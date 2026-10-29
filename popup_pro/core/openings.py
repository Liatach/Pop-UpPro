"""Openings placed by numbers: their outlines, the face they sit on, and
door flaps (cut on every side but one, which is a hinge crease). Pure
geometry on the model, no Blender data, so the model can cut doors while it
builds and the hole cutter can place holes afterwards."""

import math

from .geom import clip_halfplane, poly_area

SEG = 24  # segments in a half circle


# ------------------------------------------------------------- shapes
def shape(kind, x, y, w, h):
    """Outline (CCW) of an opening: x centre, y bottom, w wide, h tall."""
    r = 0.5 * w
    if kind == "OVAL":
        return [(x + r * math.cos(2 * math.pi * i / (2 * SEG)),
                 y + 0.5 * h + 0.5 * h * math.sin(2 * math.pi * i / (2 * SEG)))
                for i in range(2 * SEG)]
    if kind == "ARCH":
        rr = min(r, h)
        top = y + h - rr
        pts = [(x - r, y), (x + r, y), (x + r, top)]
        pts += [(x + r * math.cos(math.pi * i / SEG), top + rr * math.sin(math.pi * i / SEG))
                for i in range(1, SEG)]
        pts.append((x - r, top))
        return pts
    return [(x - r, y), (x + r, y), (x + r, y + h), (x - r, y + h)]


def face_frame(model, face):
    """Where an opening on one face of a piece sits: (origin, across, up) in
    the piece's pattern, and the face's outline to keep the hole inside it
    (None when the face isn't a single convex outline). X runs across the
    face from its centre, Y up from its bottom edge. Up is the pattern's up,
    except on a box's panels, whose folds run along the pattern: there up
    points to the fold the panel hangs from (a front's top, a top's back)."""
    p = model.panels.get(face)
    if p is None or not p.polys:
        return None
    up = (0.0, 1.0)
    if p.hinge is not None and face.startswith("Box"):
        F = p.hinge.Fc
        fy = (F.col[1][0], F.col[1][1])
        if abs(fy[0]) < 1e-6:  # fold along the pattern's y
            pts = [q for poly in p.polys for q in poly]
            cx = sum(q[0] for q in pts) / len(pts)
            up = (1.0 if F.col[3][0] > cx else -1.0, 0.0)
    across = (up[1], -up[0])
    pts = [q for poly in p.polys for q in poly]
    ss = [q[0] * across[0] + q[1] * across[1] for q in pts]
    ts = [q[0] * up[0] + q[1] * up[1] for q in pts]
    s0, t0 = 0.5 * (min(ss) + max(ss)), min(ts)
    origin = (s0 * across[0] + t0 * up[0], s0 * across[1] + t0 * up[1])
    clip = None
    if len(p.polys) == 1 and _convex(p.polys[0]):
        clip = p.polys[0]
    return origin, across, up, clip


def _convex(poly):
    n = len(poly)
    sign = 0
    for i in range(n):
        a, b, c = poly[i], poly[(i + 1) % n], poly[(i + 2) % n]
        z = (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])
        if abs(z) > 1e-9:
            if sign and (z > 0) != (sign > 0):
                return False
            sign = 1 if z > 0 else -1
    return True


def _turned(o, poly):
    turn = o.get("turn", 0.0)  # radians
    if abs(turn) <= 1e-9:
        return poly
    cx, cy = o["x"], o["y"] + 0.5 * o["height"]
    c, s_ = math.cos(turn), math.sin(turn)
    return [(cx + (x - cx) * c - (y - cy) * s_, cy + (x - cx) * s_ + (y - cy) * c)
            for x, y in poly]


def _on_face(model, o, poly, faces=True):
    fr = face_frame(model, o["face"]) if faces and o.get("face") else None
    if fr is None:
        return poly, None
    (ox, oy), a, u, clip = fr
    return [(ox + x * a[0] + y * u[0], oy + x * a[1] + y * u[1]) for x, y in poly], clip


def place(model, o, faces=True):
    """An opening's outline in its piece's pattern: shaped, turned about its
    centre, put on its face and kept inside it. o: a dict (opening_dict)."""
    poly = _turned(o, shape(o["shape"], o["x"], o["y"], o["width"], o["height"]))
    poly, clip = _on_face(model, o, poly, faces)
    if clip is not None:
        c = clip if poly_area(clip) > 0 else clip[::-1]
        for i in range(len(c)):
            p0, p1 = c[i], c[(i + 1) % len(c)]
            n = (-(p1[1] - p0[1]), p1[0] - p0[0])  # inward on a CCW outline
            L = math.hypot(*n)
            if L < 1e-9:
                continue
            n = (n[0] / L, n[1] / L)
            # stop a hair short of the folds, so the face stays joined
            poly = clip_halfplane(poly, n, n[0] * p0[0] + n[1] * p0[1] + 0.5)
            if len(poly) < 3:
                return []
    return poly




HINGES = {"RECT": {"BOTTOM": 0, "RIGHT": 1, "TOP": 2, "LEFT": 3},
          "ARCH": {"BOTTOM": 0, "RIGHT": 1, "LEFT": -1}}


def door_lines(model, o):
    """A door flap as extra lines in its piece's pattern: one cut round every
    side but the hinge, and the hinge, a crease the door turns about
    ("HINGE:<degrees open>"). Ovals take a rectangle's door."""
    kind = o["shape"] if o["shape"] in HINGES else "RECT"
    pts = shape(kind, o["x"], o["y"], o["width"], o["height"])
    i = HINGES[kind].get(o.get("hinge", "LEFT"), HINGES[kind]["LEFT"]) % len(pts)
    j = (i + 1) % len(pts)
    # the cut runs from the hinge's far end round to its near end
    cut = pts[j:] + pts[:i + 1] if j > i else pts[j:i + 1]
    hinge = [pts[i], pts[j]]
    cut, _ = _on_face(model, o, _turned(o, cut))
    hinge, _ = _on_face(model, o, _turned(o, hinge))
    return [("CUT", cut), (f"HINGE:{float(o.get('open', 60.0)):g}", hinge)]


def opening_dict(o, i=0):
    """The numbers of an opening (a Blender property group) as a dict."""
    return dict(id=i, piece=o.on_piece or ("Card" if not o.on_uid else ""),
                face=getattr(o, "face", ""), shape=o.shape, x=o.x, y=o.y, width=o.width,
                height=o.height, turn=getattr(o, "turn", 0.0),
                cut=getattr(o, "cut", "HOLE"), hinge=getattr(o, "hinge", "LEFT"),
                open=getattr(o, "door_open", 60.0))
