"""Print sheets as SVG.

Lines come from the actual mesh (so hand-edited panel shapes print as
edited). Two panel edges that lie on top of each other in the layout are a
fold if they also stay together when the card is assembled, otherwise they
are a slit (cut). Mountain or valley is read from which way the printed side
turns.

Layers: art, sketch, glue, guides, valley, mountain, cut, labels.
"""

import base64
import math
import os
import tempfile
from xml.sax.saxutils import escape

import bpy
from mathutils import Matrix, Vector

from . import live
from .art import ART_IMAGE, PRINT_IMAGE, SKETCH
from .build import TILE_MM, make_model

TOL = 0.05  # mm, collinear test
JOIN = 0.6  # mm, edges this close in the assembled card count as one fold

GUIDE = 'fill="none" stroke="#7a7a7a" stroke-width="0.25" stroke-dasharray="0.6 1.2"'
GLUE = 'fill="#d9d4c7" fill-opacity="0.7" stroke="none"'
CONTENT = ("PRINT", "CUT", "CREASE", "LINES")
LINE_STYLES = ("DEFAULT", "CUSTOM", "NONE")


def _hex(rgb):
    return "#" + "".join(f"{max(0, min(255, int(round(c * 255)))):02x}" for c in rgb[:3])


def line_styles(content="PRINT", style="DEFAULT", width=0.3, color=(0, 0, 0),
                opacity=1.0, dashed=True):
    """SVG attributes for cut / mountain / valley lines. Lines-only content
    always uses the chosen colour (default black) at the chosen opacity."""
    w = f"{width:.3g}"
    base = f'fill="none" stroke-width="{w}" stroke-linecap="round" stroke-linejoin="round"'
    dm = f' stroke-dasharray="{width * 12:.3g} {width * 4:.3g} {width * 2:.3g} {width * 4:.3g}"'
    dv = f' stroke-dasharray="{width * 6:.3g} {width * 4:.3g}"'
    if not dashed:
        dm = dv = ""
    if content != "PRINT" or style == "CUSTOM":
        if content != "PRINT" and style != "CUSTOM":
            opacity = 1.0
        c = f' stroke="{_hex(color)}" stroke-opacity="{max(0.0, min(1.0, opacity)):.3g}"'
        return {"cut": base + c, "mountain": base + c + dm, "valley": base + c + dv}
    out = {"cut": base + ' stroke="#000000"', "mountain": base + ' stroke="#c0182a"' + dm,
           "valley": base + ' stroke="#1d5fbf"' + dv}
    if style == "NONE":
        out = {k: v + ' display="none"' for k, v in out.items()}
    return out


def settings_from(st):
    """Export keyword arguments from the scene's Pop-up settings."""
    return dict(content=st.export_content, line_style=st.line_style,
                line_color=tuple(st.line_color), line_opacity=st.line_opacity,
                line_width=st.line_width, dashed=st.dashed_folds,
                include_art=st.export_art, include_sketch=st.export_sketch,
                include_guides=st.export_guides, include_labels=st.export_labels)


class Seg:
    __slots__ = ("panel", "a", "b", "face", "marks")

    def __init__(self, panel, a, b, face):
        self.panel, self.a, self.b, self.face = panel, a, b, face
        self.marks = []  # (t0, t1, kind) kind: "skip" or ("fold", type)


def _collinear_overlap(s, o):
    d = s.b - s.a
    L = d.length
    if L < 1e-9:
        return None
    u = d / L
    nrm = Vector((-u.y, u.x))
    if abs((o.a - s.a).dot(nrm)) > TOL or abs((o.b - s.a).dot(nrm)) > TOL:
        return None
    t0, t1 = sorted(((o.a - s.a).dot(u) / L, (o.b - s.a).dot(u) / L))
    lo, hi = max(0.0, t0), min(1.0, t1)
    if (hi - lo) * L < TOL * 4:
        return None
    return lo, hi


def _interval_other(s, o, lo, hi):
    """Map an overlap interval on s to o's parameter range."""
    pa = s.a.lerp(s.b, lo)
    pb = s.a.lerp(s.b, hi)
    d = o.b - o.a
    L2 = d.length_squared
    ta = (pa - o.a).dot(d) / L2
    tb = (pb - o.a).dot(d) / L2
    return min(ta, tb), max(ta, tb)


def _free_parts(marks):
    """Uncovered sub-intervals of [0, 1]."""
    cuts = []
    pos = 0.0
    for t0, t1, _ in sorted(marks):
        if t0 > pos + 1e-6:
            cuts.append((pos, t0))
        pos = max(pos, t1)
    if pos < 1 - 1e-6:
        cuts.append((pos, 1.0))
    return cuts


class Affine:
    """2D affine (a c e / b d f) as used by SVG matrix()."""

    def __init__(self, a=1, b=0, c=0, d=1, e=0, f=0):
        self.m = (a, b, c, d, e, f)

    def __matmul__(self, o):
        a, b, c, d, e, f = self.m
        A, B, C, D, E, F = o.m
        return Affine(a * A + c * B, b * A + d * B, a * C + c * D, b * C + d * D,
                      a * E + c * F + e, b * E + d * F + f)

    def svg(self):
        return "matrix(" + " ".join(f"{v:.6g}" for v in self.m) + ")"

    @staticmethod
    def from4(M):
        return Affine(M[0][0], M[1][0], M[0][1], M[1][1], M[0][3], M[1][3])


def _fmt(p):
    return f"{p[0]:.3f},{p[1]:.3f}"


def _tile_pngs(img, tmp):
    """Write every UDIM tile of an image to PNG; returns {tile: path}."""
    if img is None:
        return {}
    base = os.path.join(tmp, "tile")
    keep = img.filepath_raw, img.file_format
    out = {}
    try:
        img.filepath_raw = base + ".<UDIM>.png"
        img.file_format = "PNG"
        img.save()
        for t in img.tiles:
            p = f"{base}.{t.number}.png"
            if os.path.exists(p):
                out[t.number] = p
    except RuntimeError:
        return {}
    finally:
        try:
            img.filepath_raw, img.file_format = keep
        except Exception:
            pass
    return out


def export(scene, filepath, include_art=True, include_sketch=True, include_guides=True,
           include_labels=True, content="PRINT", line_style="DEFAULT",
           line_color=(0.0, 0.0, 0.0), line_opacity=1.0, line_width=0.3, dashed=True):
    st = scene.popup
    rig = st.rig
    STYLE = line_styles(content, line_style, line_width, line_color, line_opacity, dashed)
    if content != "PRINT":
        include_art = include_sketch = include_guides = include_labels = False
    show = {"cut": content in ("PRINT", "CUT", "LINES"),
            "fold": content in ("PRINT", "CREASE", "LINES")}
    meta = live.meta(rig)
    if meta is None or st.layout is None:
        raise RuntimeError("build the card first")
    model, layout = make_model(scene)
    names = [p["name"] for p in meta["panels"]]
    if names != model.order:
        raise RuntimeError("settings changed since the last build: rebuild first")
    mmu = meta["mm_per_unit"]
    mesh = st.layout.data
    attr = mesh.attributes.get("pop_panel")
    if attr is None:
        raise RuntimeError("the card mesh has lost its panel attribute")
    prints = layout["prints"]
    sheets = meta["sheets"]
    panel_info = meta["panels"]

    def D(name, t):
        p = model.panels[name]
        return p.asm(t) @ prints[p.piece].inverted()

    D90 = {n: D(n, 90.0) for n in names}
    D40 = {n: D(n, 40.0) for n in names}

    co = [Vector((v.co.x * mmu, v.co.y * mmu)) for v in mesh.vertices]
    faces_by_piece = {}
    segs_by_piece = {}
    edge_count = {}
    for f in mesh.polygons:
        pi = attr.data[f.index].value
        if pi >= len(names):
            continue
        vs = list(f.vertices)
        for i in range(len(vs)):
            k = (pi, min(vs[i], vs[(i + 1) % len(vs)]), max(vs[i], vs[(i + 1) % len(vs)]))
            edge_count[k] = edge_count.get(k, 0) + 1
    for f in mesh.polygons:
        pi = attr.data[f.index].value
        if pi >= len(names):
            continue
        piece = panel_info[pi]["piece"]
        faces_by_piece.setdefault(piece, []).append((pi, [co[v] for v in f.vertices], f))
        vs = list(f.vertices)
        for i in range(len(vs)):
            a, b = vs[i], vs[(i + 1) % len(vs)]
            if edge_count[(pi, min(a, b), max(a, b))] == 1:
                segs_by_piece.setdefault(piece, []).append(Seg(pi, co[a], co[b], f))

    def centroid(face):
        return sum((co[v] for v in face.vertices), Vector((0, 0))) / len(face.vertices)

    # ---- classify overlapping edges
    for piece, segs in segs_by_piece.items():
        for i, s in enumerate(segs):
            for j in range(i + 1, len(segs)):
                o = segs[j]
                ov = _collinear_overlap(s, o)
                if ov is None:
                    continue
                lo, hi = ov
                if o.panel == s.panel:  # split inside one panel: no line
                    olo, ohi = _interval_other(s, o, lo, hi)
                    s.marks.append((lo, hi, ("skip",)))
                    o.marks.append((olo, ohi, ("skip",)))
                    continue
                ns, no = names[s.panel], names[o.panel]
                fold = True
                for tt in (lo, 0.5 * (lo + hi), hi):
                    p = s.a.lerp(s.b, tt).to_3d()
                    for Dm in (D90, D40):
                        if ((Dm[ns] @ p) - (Dm[no] @ p)).length > JOIN:
                            fold = False
                olo, ohi = _interval_other(s, o, lo, hi)
                if fold:
                    mid = s.a.lerp(s.b, 0.5 * (lo + hi)).to_3d()
                    Ms, Mo = D(ns, 60.0), D(no, 60.0)
                    n = (Ms.to_3x3() @ Vector((0, 0, 1))).normalized()
                    v = Mo @ centroid(o.face).to_3d() - Ms @ mid
                    kind = "valley" if n.dot(v) > 0 else "mountain"
                    s.marks.append((lo, hi, ("fold", kind)))
                else:
                    s.marks.append((lo, hi, ("cut",)))
                o.marks.append((olo, ohi, ("skip",)))

    # ---- art tiles
    tmp = tempfile.mkdtemp(prefix="popup_svg_")
    tiles = {}
    if include_art:
        img = bpy.data.images.get(PRINT_IMAGE) or bpy.data.images.get(ART_IMAGE)
        if img is not None:
            tiles = _tile_pngs(img, tmp)

    # ---- sketch strokes, grouped by piece, in layout mm
    strokes_by_piece = {}
    sk = bpy.data.objects.get(SKETCH)
    if include_sketch and sk is not None and sk.type == "GREASEPENCIL":
        gp = sk.data
        for layer in gp.layers:
            if layer.hide or layer.parent != rig or layer.parent_bone not in names:
                continue
            bone = rig.data.bones.get(layer.parent_bone)
            if bone is None:
                continue
            M = bone.matrix_local @ layer.matrix_parent_inverse @ layer.matrix_local
            piece = panel_info[names.index(layer.parent_bone)]["piece"]
            frame = layer.current_frame()
            if frame is None or frame.drawing is None:
                continue
            for stroke in frame.drawing.strokes:
                pts = [M @ Vector(p.position) * mmu for p in stroke.points]
                if not pts:
                    continue
                mat = gp.materials[stroke.material_index] if stroke.material_index < len(gp.materials) else None
                col = (0, 0, 0, 1)
                fill = None
                if mat is not None and mat.grease_pencil:
                    g = mat.grease_pencil
                    col = tuple(g.color)
                    if g.show_fill:
                        fill = tuple(g.fill_color)
                    if not g.show_stroke:
                        col = None
                vc = stroke.points[0].vertex_color
                if col is not None and vc[3] > 0:
                    col = tuple(col[i] * (1 - vc[3]) + vc[i] * vc[3] for i in range(3)) + (col[3],)
                rad = sum(p.radius for p in stroke.points) / len(stroke.points)
                width = max(0.05, 2 * (rad + layer.radius_offset) * mmu)
                op = layer.opacity * (sum(p.opacity for p in stroke.points) / len(stroke.points))
                strokes_by_piece.setdefault(piece, []).append(
                    (pts, col, fill, width, op, stroke.cyclic))

    def hexcol(c):
        lin = lambda x: (12.92 * x if x <= 0.0031308 else 1.055 * x ** (1 / 2.4) - 0.055)
        return "#" + "".join(f"{int(max(0, min(1, lin(v))) * 255 + 0.5):02x}" for v in c[:3])

    # ---- guides: where each tab is glued, drawn on the piece it glues to
    guides = {}
    if include_guides:
        for pi, p in enumerate(panel_info):
            if p["kind"] != "tab":
                continue
            host = model.panels[model.panels[p["name"]].parent]
            Mp = prints[host.piece] @ host.asm(90.0).inverted() @ D90[p["name"]]
            for piece_faces in faces_by_piece.get(p["piece"], []):
                if piece_faces[0] == pi:
                    guides.setdefault(host.piece, []).append(
                        [(Mp @ q.to_3d()).to_2d() for q in piece_faces[1]])

    written = []
    root, ext = os.path.splitext(filepath)
    for si, sh in enumerate(sheets):
        SW, SH = sh["size"]
        ox, oy = sh["origin"]

        def P(q):
            return (q[0] - ox, SH - (q[1] - oy))

        flip = Affine(1, 0, 0, -1, -ox, SH + oy)
        pieces = [k for k, v in meta["pieces"].items() if v["sheet"] == si]
        L = {k: [] for k in ("art", "sketch", "glue", "guides", "valley", "mountain",
                             "cut", "labels")}
        defs = []
        for piece in pieces:
            faces = faces_by_piece.get(piece, [])
            info = meta["pieces"][piece]
            clip_id = f"clip_{piece.replace('.', '_')}"
            if faces:
                d = " ".join("M" + " L".join(_fmt(P(q)) for q in pts) + " Z"
                             for _, pts, _ in faces)
                defs.append(f'<clipPath id="{clip_id}" clipPathUnits="userSpaceOnUse">'
                            f'<path d="{d}"/></clipPath>')
            # art
            tile = tiles.get(1001 + info["slot"])
            if tile:
                if info["is_card"]:
                    W, H = meta["W"], meta["H"]
                    x0, y1, w, h = -W, H, 2 * W, H
                else:
                    ax, ay = info["anchor"]
                    x0, y1, w, h = ax - TILE_MM / 2, ay + TILE_MM / 2, TILE_MM, TILE_MM
                with open(tile, "rb") as fh:
                    data = base64.b64encode(fh.read()).decode("ascii")
                M = flip @ Affine.from4(prints[piece]) @ Affine(1, 0, 0, -1, x0, y1)
                L["art"].append(
                    f'<g clip-path="url(#{clip_id})"><image width="{w:.3f}" height="{h:.3f}" '
                    f'preserveAspectRatio="none" transform="{M.svg()}" '
                    f'href="data:image/png;base64,{data}"/></g>')
            # sketch
            sks = strokes_by_piece.get(piece, [])
            if sks:
                out = []
                for pts, col, fill, width, op, cyc in sks:
                    d = "M" + " L".join(_fmt(P(q)) for q in pts) + (" Z" if cyc or fill else "")
                    attrs = [f'opacity="{op:.3g}"']
                    attrs.append(f'fill="{hexcol(fill)}"' if fill else 'fill="none"')
                    if col is not None:
                        attrs.append(f'stroke="{hexcol(col)}" stroke-width="{width:.3f}" '
                                     f'stroke-linecap="round" stroke-linejoin="round"')
                    out.append(f'<path d="{d}" {" ".join(attrs)}/>')
                L["sketch"].append(f'<g clip-path="url(#{clip_id})">' + "".join(out) + "</g>")
            # glue
            for pi, pts, _ in faces:
                if panel_info[pi]["kind"] == "tab":
                    if content == "PRINT":
                        L["glue"].append(f'<path d="M{" L".join(_fmt(P(q)) for q in pts)} '
                                         f'Z" {GLUE}/>')
            # lines
            for s in segs_by_piece.get(piece, []):
                for t0, t1, kind in s.marks:
                    if kind[0] == "fold" and show["fold"]:
                        a, b = s.a.lerp(s.b, t0), s.a.lerp(s.b, t1)
                        L[kind[1]].append(f'<path d="M{_fmt(P(a))} L{_fmt(P(b))}" '
                                          f'{STYLE[kind[1]]}/>')
                    elif kind[0] == "cut" and show["cut"]:
                        a, b = s.a.lerp(s.b, t0), s.a.lerp(s.b, t1)
                        L["cut"].append(f'<path d="M{_fmt(P(a))} L{_fmt(P(b))}" {STYLE["cut"]}/>')
                for t0, t1 in (_free_parts(s.marks) if show["cut"] else []):
                    a, b = s.a.lerp(s.b, t0), s.a.lerp(s.b, t1)
                    L["cut"].append(f'<path d="M{_fmt(P(a))} L{_fmt(P(b))}" {STYLE["cut"]}/>')
            if include_labels and faces:
                xs = [P(q)[0] for _, pts, _ in faces for q in pts]
                ys = [P(q)[1] for _, pts, _ in faces for q in pts]
                if info["is_card"]:
                    lx, ly = min(xs) + 3, max(ys) - 2
                else:
                    lx, ly = min(xs), max(ys) + 3.2
                L["labels"].append(f'<text x="{lx:.2f}" y="{ly:.2f}" font-size="2.8" '
                                   f'font-family="sans-serif" fill="#8a8a8a">'
                                   f'{escape(info["label"])}</text>')
        for piece in pieces:
            for g in guides.get(piece, []):
                L["guides"].append(f'<path d="M{" L".join(_fmt(P(q)) for q in g)} Z" '
                                   f'{GUIDE}/>')
        body = []
        for name in ("art", "sketch", "glue", "guides", "valley", "mountain", "cut", "labels"):
            body.append(f'<g id="{name}" inkscape:groupmode="layer" inkscape:label="{name}">'
                        + "".join(L[name]) + "</g>")
        svg = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape" '
            f'width="{SW:.2f}mm" height="{SH:.2f}mm" viewBox="0 0 {SW:.3f} {SH:.3f}">\n'
            f'<defs>{"".join(defs)}</defs>\n' + "\n".join(body) + "\n</svg>\n")
        suffix = {"CUT": "_cut", "CREASE": "_crease", "LINES": "_lines"}.get(content, "")
        path = f"{root}{suffix}_sheet{si + 1}.svg"
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(svg)
        written.append(path)
    return written
