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
from .naming import N
from .art import ART_IMAGE, PRINT_IMAGE, SKETCH
from .build import TILE_MM, make_model

TOL = 0.05  # mm, collinear test
JOIN = 0.6  # mm, edges this close in the assembled card count as one fold

GUIDE = 'fill="none" stroke="#7a7a7a" stroke-width="0.25" stroke-dasharray="0.6 1.2"'
CONTENT = ("PRINT", "ART_CUT", "CUT", "CREASE", "LINES")
SUFFIX = {"ART_CUT": "_art", "CUT": "_cut", "CREASE": "_crease", "LINES": "_lines"}
CREASE_RED = "#ff0000"  # Cut + Crease: creases import as their own colour layer
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
    lines_only = content in ("CUT", "CREASE", "LINES")
    if lines_only or style == "CUSTOM":
        if lines_only and style != "CUSTOM":
            opacity = 1.0
        c = f' stroke="{_hex(color)}" stroke-opacity="{max(0.0, min(1.0, opacity)):.3g}"'
        f = c
        if content == "LINES":
            f = f' stroke="{CREASE_RED}" stroke-opacity="{max(0.0, min(1.0, opacity)):.3g}"'
        return {"cut": base + c, "mountain": base + f + dm, "valley": base + f + dv}
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
                include_guides=st.export_guides, include_labels=st.export_labels,
                tab_fill=st.tab_fill, tab_color=tuple(st.tab_color), bleed=st.bleed,
                include_reverse=st.export_reverse, include_layout=st.export_layout)


def inflate(poly, d, miter=3.0):
    """Grow a convex CCW polygon outward by d (miter joins, clamped)."""
    n = len(poly)
    if d <= 0 or n < 3:
        return poly
    out = []
    for i in range(n):
        a, b, c = Vector(poly[i - 1]), Vector(poly[i]), Vector(poly[(i + 1) % n])
        e1, e2 = (b - a), (c - b)
        if e1.length < 1e-9 or e2.length < 1e-9:
            out.append(tuple(b))
            continue
        n1 = Vector((e1.y, -e1.x)).normalized()  # outward for CCW
        n2 = Vector((e2.y, -e2.x)).normalized()
        m = n1 + n2
        if m.length < 1e-6:
            out.append(tuple(b + n1 * d))
            continue
        m.normalize()
        k = min(d / max(m.dot(n1), 1e-6), miter * d)
        out.append(tuple(b + m * k))
    return out


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
           line_color=(0.0, 0.0, 0.0), line_opacity=1.0, line_width=0.3, dashed=True,
           tab_fill=False, tab_color=(0.85, 0.83, 0.78), bleed=0.0, include_reverse=True,
           include_layout=True):
    """content: PRINT (art, tabs, guides, labels, all lines), ART_CUT (art and
    tabs outlined by cut lines only: nothing drawn over the art), or for
    cutting machines CUT, CREASE, LINES (plain solid strokes, no art or text;
    LINES draws creases red). tab_fill colours plain tabs (else paper white).
    bleed (mm) lets the art run past each piece's outline.
    With guides on (PRINT), a piece that has tabs glued to its back gets a
    mirrored reverse sheet to print on the other side of its sheet, and
    include_layout adds an assembly page: where every part glues on the card
    and a parts list."""
    st = scene.popup
    rig = st.rig
    STYLE = line_styles(content, line_style, line_width, line_color, line_opacity, dashed)
    if content in ("CUT", "CREASE", "LINES"):
        include_art = include_sketch = include_guides = include_labels = False
        tab_fill = False
        bleed = 0.0
    if content == "ART_CUT":
        include_guides = include_labels = False
    if content != "PRINT":
        include_layout = False
    if content not in ("PRINT", "ART_CUT"):
        include_reverse = False
    show = {"cut": content in ("PRINT", "ART_CUT", "CUT", "LINES"),
            "fold": content in ("PRINT", "CREASE", "LINES")}
    glue_style = (f'fill="{_hex(tab_color)}" stroke="none"' if tab_fill else None)
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

    tr = model.t_ref  # 90 for a card, half the stage angle in a carousel
    D90 = {n: D(n, tr) for n in names}
    D40 = {n: D(n, tr * 4.0 / 9.0) for n in names}

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
                if o.panel == s.panel or frozenset((names[s.panel], names[o.panel])) in model.soft:
                    # split inside one panel, or a strip sliding through a slit: no line
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
                    Ms, Mo = D(ns, tr * 2.0 / 3.0), D(no, tr * 2.0 / 3.0)
                    n = (Ms.to_3x3() @ Vector((0, 0, 1))).normalized()
                    v = Mo @ centroid(o.face).to_3d() - Ms @ mid
                    kind = "valley" if n.dot(v) > 0 else "mountain"
                    s.marks.append((lo, hi, ("fold", kind)))
                else:
                    s.marks.append((lo, hi, ("cut",)))
                o.marks.append((olo, ohi, ("skip",)))

    # ---- art tiles
    tmp = tempfile.mkdtemp(prefix="popup_svg_")
    from . import images as _images
    placed_png = {}

    def placed(pl, piece, T):
        """An <image> for a placed image: T maps pattern mm to the sheet."""
        key = pl.image.name
        if key not in placed_png:
            got = _images.png_data(pl.image, tmp)
            if got is None:
                placed_png[key] = None
            else:
                with open(got[0], "rb") as fh:
                    placed_png[key] = base64.b64encode(fh.read()).decode("ascii")
        data = placed_png[key]
        if data is None:
            return ""
        out = []
        for k in range(max(1, pl.repeat)):  # copies side by side
            m = _images.svg_matrix(pl, meta, k)
            if m is None:
                return ""
            M = T @ Affine.from4(prints[piece]) @ Affine(*m)
            out.append(f'<image width="1" height="1" preserveAspectRatio="none" '
                       f'opacity="{pl.opacity:.3g}" transform="{M.svg()}" '
                       f'href="data:image/png;base64,{data}"/>')
        return "".join(out)
    tiles = {}
    if include_art:
        img = bpy.data.images.get(N(scene, PRINT_IMAGE)) or bpy.data.images.get(N(scene, ART_IMAGE))
        if img is not None:
            tiles = _tile_pngs(img, tmp)

    # ---- sketch strokes, grouped by piece, in layout mm
    strokes_by_piece = {}
    sk = bpy.data.objects.get(N(scene, SKETCH))
    if include_sketch and sk is not None and sk.type == "GREASEPENCIL":
        gp = sk.data
        for layer in gp.layers:
            if layer.hide or layer.parent != rig or layer.parent_bone not in names:
                continue
            if layer.name.endswith(" cut"):
                continue  # hole outlines: cut out of the mesh, printed as cut lines
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
    back_guides = {}  # glued to the back of a piece: drawn on its reverse sheet
    joins = []  # (tab's piece, host piece, back?) for the parts list
    for pi, p in enumerate(panel_info):
        if p["kind"] != "tab":
            continue
        host = model.panels[model.panels[p["name"]].parent]
        rel = host.asm(tr).inverted() @ D90[p["name"]]
        Mp = prints[host.piece] @ rel
        for piece_faces in faces_by_piece.get(p["piece"], []):
            if piece_faces[0] == pi:
                back = (rel @ piece_faces[1][0].to_3d()).z < 0
                if (p["piece"], host.piece, back) not in joins and p["piece"] != host.piece:
                    joins.append((p["piece"], host.piece, back))
                poly = [(Mp @ q.to_3d()).to_2d() for q in piece_faces[1]]
                (back_guides if back else guides).setdefault(host.piece, []).append(
                    (poly, p["piece"]))

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
                d = " ".join("M" + " L".join(_fmt(P(q)) for q in inflate(pts, bleed)) + " Z"
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
            # placed images, full size, over the art
            if include_art and faces:
                got = "".join(placed(pl, piece, flip)
                              for pl in _images.for_piece(scene, piece, "FRONT"))
                if got:
                    L["art"].append(f'<g clip-path="url(#{clip_id})">{got}</g>')
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
            # tab colour (plain tabs stay paper white unless asked)
            for pi, pts, _ in faces:
                if panel_info[pi]["kind"] == "tab" and glue_style:
                    L["glue"].append(f'<path d="M{" L".join(_fmt(P(q)) for q in inflate(pts, bleed))} '
                                     f'Z" {glue_style}/>')
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
                note = (" (back: reverse sheet)"
                        if include_reverse and include_guides and back_guides.get(piece) else "")
                L["labels"].append(f'<text x="{lx:.2f}" y="{ly:.2f}" font-size="2.8" '
                                   f'font-family="sans-serif" fill="#8a8a8a">'
                                   f'{escape(info["label"] + note)}</text>')
        for piece in pieces:
            for g, _src in (guides.get(piece, []) if include_guides else []):
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
        suffix = SUFFIX.get(content, "")
        path = f"{root}{suffix}_sheet{si + 1}.svg"
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(svg)
        written.append(path)
        # ---- reverse: tab markers for the back of this sheet's pieces
        rev = [pc for pc in pieces if back_guides.get(pc)] if include_guides else []
        mirror = Affine(-1, 0, 0, 1, SW, 0) @ flip
        back_art = {}
        if include_art:
            for pc in pieces:
                got = "".join(placed(pl, pc, mirror)
                              for pl in _images.for_piece(scene, pc, "BACK"))
                if got and faces_by_piece.get(pc):
                    back_art[pc] = got
        if include_reverse and (rev or back_art):
            path = f"{root}{suffix}_sheet{si + 1}_reverse.svg"
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(_reverse_svg(si, SW, SH, P, pieces, rev, segs_by_piece, faces_by_piece,
                                      back_guides, meta, back_art, bleed,
                                      notes=include_guides))
            written.append(path)
    if include_layout:
        path = f"{root}_layout.svg"
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(_layout_svg(sheets[0], faces_by_piece, segs_by_piece, guides, back_guides,
                                 joins, meta))
        written.append(path)
    return written


FAINT = 'fill="none" stroke="#b8b8b8" stroke-width="0.2"'
MARK = 'fill="#fff3c4" stroke="#6b5b2a" stroke-width="0.3" stroke-dasharray="1 0.8"'
TEXT = 'font-family="sans-serif" fill="#333333"'


def _svg_doc(SW, SH, body):
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape" '
            f'width="{SW:.2f}mm" height="{SH:.2f}mm" viewBox="0 0 {SW:.3f} {SH:.3f}">\n'
            + body + "\n</svg>\n")


def _outline(segs, P):
    return "".join(f'<path d="M{_fmt(P(s.a))} L{_fmt(P(s.b))}" {FAINT}/>' for s in segs
                   if not any(k[0] in ("fold", "skip") for _, _, k in s.marks))


def _reverse_svg(si, SW, SH, P, pieces, rev, segs_by_piece, faces_by_piece, back_guides,
                 meta, back_art=None, bleed=0.0, notes=True):
    """The back of a sheet, mirrored left to right so it lines up when printed
    on the other side: images placed on the backs of pieces, faint outlines
    of every piece, the glue markers for tabs that stick to the back, and
    labels that read the right way round."""
    def R(q):
        x, y = P(q)
        return (SW - x, y)

    out = []
    for piece, got in (back_art or {}).items():
        cid = f"back_{piece.replace('.', '_')}"
        d = " ".join("M" + " L".join(_fmt(R(q)) for q in inflate(pts, bleed)) + " Z"
                     for _, pts, _ in faces_by_piece.get(piece, []))
        out.append(f'<defs><clipPath id="{cid}" clipPathUnits="userSpaceOnUse">'
                   f'<path d="{d}"/></clipPath></defs>'
                   f'<g clip-path="url(#{cid})">{got}</g>')
    if not notes:
        return _svg_doc(SW, SH, "\n".join(out))
    for piece in pieces:
        out.append(_outline(segs_by_piece.get(piece, []), R))
    for piece in rev:
        for g, src in back_guides[piece]:
            out.append(f'<path d="M{" L".join(_fmt(R(q)) for q in g)} Z" {MARK}/>')
            c = sum((Vector(R(q)) for q in g), Vector((0, 0))) / len(g)
            out.append(f'<text x="{c.x:.2f}" y="{c.y + 1:.2f}" font-size="2.4" '
                       f'text-anchor="middle" {TEXT}>glue {escape(meta["pieces"][src]["label"])}'
                       f'</text>')
        pts = [R(q) for _, f, _ in faces_by_piece.get(piece, []) for q in f]
        if pts:
            x = sum(q[0] for q in pts) / len(pts)
            y = max(q[1] for q in pts) + 4
            out.append(f'<text x="{x:.2f}" y="{y:.2f}" font-size="3.2" font-weight="bold" '
                       f'text-anchor="middle" {TEXT}>BACK of {escape(meta["pieces"][piece]["label"])}'
                       f'</text>')
    flip = "short" if SW > SH else "long"
    out.append(f'<text x="6" y="8" font-size="5" font-weight="bold" {TEXT}>'
               f'REVERSE OF SHEET {si + 1}</text>')
    out.append(f'<text x="6" y="13" font-size="3" {TEXT}>Print on the back of sheet {si + 1} '
               f'(double-sided, flip on {flip} edge), or hold up to the light and copy the '
               f'markers. Grey outlines should sit behind the cut lines.</text>')
    return _svg_doc(SW, SH, "\n".join(out))


PALETTE = ("#e8d5a3", "#b9d7c4", "#c9c3e6", "#f2bfb0", "#b7d3e8", "#e3c9dc", "#d9e3b0")


def _layout_svg(sheet, faces_by_piece, segs_by_piece, guides, back_guides, joins, meta):
    """Assembly page: the open card with every part's glue footprint shaded
    and numbered, and a parts list saying which sheet each part is on and
    what it glues to."""
    SW, SH = sheet["size"]
    ox, oy = sheet["origin"]
    pieces = [k for k, v in meta["pieces"].items() if not v["is_card"]]
    num = {pc: i + 1 for i, pc in enumerate(pieces)}
    rows = len(pieces) + 3
    H2 = SH + 8 + 5 * rows

    def P(q):
        return (q[0] - ox, SH - (q[1] - oy))

    out = [f'<rect x="0" y="0" width="{SW:.2f}" height="{H2:.2f}" fill="#ffffff"/>']
    out.append(_outline(segs_by_piece.get("Card", []), P))
    for s in segs_by_piece.get("Card", []):  # the spine and other creases, faint
        for t0, t1, k in s.marks:
            if k[0] == "fold":
                a, b = s.a.lerp(s.b, t0), s.a.lerp(s.b, t1)
                out.append(f'<path d="M{_fmt(P(a))} L{_fmt(P(b))}" {FAINT} '
                           f'stroke-dasharray="2 1"/>')
    for g, src in guides.get("Card", []):
        col = PALETTE[(num.get(src, 1) - 1) % len(PALETTE)]
        out.append(f'<path d="M{" L".join(_fmt(P(q)) for q in g)} Z" fill="{col}" '
                   f'stroke="#6b6b6b" stroke-width="0.25"/>')
    placed = set()
    for g, src in guides.get("Card", []):
        if src in placed:
            continue
        placed.add(src)
        q = [P(v) for v in g]
        c = (sum(v[0] for v in q) / len(q), sum(v[1] for v in q) / len(q))
        out.append(f'<circle cx="{c[0]:.2f}" cy="{c[1]:.2f}" r="2.6" fill="#ffffff" '
                   f'stroke="#333333" stroke-width="0.3"/>')
        out.append(f'<text x="{c[0]:.2f}" y="{c[1] + 1.1:.2f}" font-size="3" '
                   f'text-anchor="middle" font-weight="bold" {TEXT}>{num.get(src, "?")}</text>')
    y = SH + 8
    out.append(f'<text x="6" y="{y:.2f}" font-size="4.5" font-weight="bold" {TEXT}>'
               f'Assembly: parts and where they glue</text>')
    y += 6
    for pc in pieces:
        info = meta["pieces"][pc]
        onto = []
        for a, b, back in joins:
            if a == pc:
                name = "the card" if meta["pieces"][b]["is_card"] else meta["pieces"][b]["label"]
                onto.append(f"the back of {name}" if back else name)
        text = f'{num[pc]}. {info["label"]} (sheet {info["sheet"] + 1})'
        if onto:
            text += ": tabs glue to " + ", ".join(onto)
        if any(b == pc and back for a, b, back in joins):
            text += f'. Glue markers for its back are on sheet {info["sheet"] + 1} reverse'
        text += "."
        col = PALETTE[(num[pc] - 1) % len(PALETTE)]
        out.append(f'<rect x="6" y="{y - 3:.2f}" width="4" height="4" fill="{col}" '
                   f'stroke="#6b6b6b" stroke-width="0.2"/>')
        out.append(f'<text x="12" y="{y:.2f}" font-size="3.2" {TEXT}>{escape(text)}</text>')
        y += 5
    return _svg_doc(SW, H2, "\n".join(out))
