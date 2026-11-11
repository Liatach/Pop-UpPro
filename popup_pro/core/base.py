"""What every mechanism is made of: panels, hinges, pieces of paper and hosts
(the folds things stand on), with the card sizes and the round-end geometry
shared by tubes.

model.py has the module's overview and the Model class."""
import math

from mathutils import Matrix, Vector

from .geom import Z, ccw, clip_halfplane

T_MIN = 0.05  # degrees; avoids the degenerate fully-closed pose
TAB_LIFT = 0.15  # mm a glued tab floats above the page (avoids z-fighting)
ROUND_FACETS = 8  # panels a round tube wall half is made of


def _round_reach(d, n):
    """How far across a round half reaches, per unit length, with each of
    its n facets turned d further than the last (the middle of the first
    turned d / 2 off the side wall)."""
    return sum(math.sin((k + 0.5) * d) for k in range(n)) / n


def _round_peak(n):
    lo, hi = 0.0, math.pi / n * 2.0
    for _ in range(60):  # the reach rises then falls: find where it peaks
        m1, m2 = lo + (hi - lo) / 3.0, hi - (hi - lo) / 3.0
        if _round_reach(m1, n) < _round_reach(m2, n):
            lo = m1
        else:
            hi = m2
    return 0.5 * (lo + hi)


ROUND_DMAX = _round_peak(ROUND_FACETS)
ROUND_FMAX = _round_reach(ROUND_DMAX, ROUND_FACETS)  # about 0.72


def arcade(L, w, bays, top, sill, pillar, arch=True):
    """A strip L long (s down from its top edge) and w wide (v across) with
    bays openings between pillars, under a band top deep and over a sill
    (0: open at the bottom), as polygons that share edges (one sheet).
    arch: the openings' tops are half circles."""
    bays = max(1, int(bays))
    bw = (w - (bays + 1) * pillar) / bays
    if bw < 1.0 or L - top - sill < 2.0:
        return None
    r = 0.5 * bw
    s_spring = top + (r + 0.8 if arch else 0.0)
    if arch and L - sill - s_spring < 1.0:
        return None
    out = [[(0.0, 0.0), (top, 0.0), (top, w), (0.0, w)]]
    if sill > 1e-6:
        out.append([(L - sill, 0.0), (L, 0.0), (L, w), (L - sill, w)])
    for i in range(bays + 1):
        v0 = i * (pillar + bw)
        out.append([(top, v0), (L - sill, v0), (L - sill, v0 + pillar), (top, v0 + pillar)])
        if arch and i < bays:
            a0, a1 = v0 + pillar, v0 + pillar + bw
            vc = 0.5 * (a0 + a1)
            arc = [(s_spring - r * math.sin(math.pi * j / 16), vc - r * math.cos(math.pi * j / 16))
                   for j in range(17)]
            out.append([(top, a0)] + arc + [(top, a1)])
    return out


def round_arc(x, L, n):
    """A round tube wall half, length L, from a side wall's end to the
    mirror plane x across, as n flat facets turning evenly: straight when
    shut, round as it opens (a quarter circle across when the facets turn
    through 90 degrees between them). Points along it as (across, along)
    from the side wall's end."""
    r = min(max(x / L, 0.0), ROUND_FMAX)
    lo, hi = 0.0, ROUND_DMAX
    for _ in range(48):
        mid = 0.5 * (lo + hi)
        if _round_reach(mid, n) < r:
            lo = mid
        else:
            hi = mid
    d = 0.5 * (lo + hi)
    out = [(0.0, 0.0)]
    l_ = L / n
    for k in range(n):
        px, py = out[-1]
        th = (k + 0.5) * d
        out.append((px + l_ * math.sin(th), py + l_ * math.cos(th)))
    return out
SAMPLES = [0.5, 5, 15, 30, 45, 60, 75, 90, 105, 120, 135, 150, 165, 180]

IN = 25.4
NO_HOST = ("FLAP", "TETHER", "ROOF", "PICTURE")
CORNERS = ("KFL", "KFR", "KBR", "KBL", "KF", "KB")  # a tube's inside corners (towers stand there)


def _card(w, h, label, desc):
    return (w, h, (2 * w, h), label, desc)


CARD_PRESETS = {
    # key: (page width W (spine to edge), spine length H, open sheet, label, help)
    "A6": _card(105.0, 148.5, "A6 (A5 folded)", "105 x 148 mm card from an A5 sheet"),
    "A5": _card(148.5, 210.0, "A5 (A4 folded)", "148 x 210 mm card from an A4 sheet"),
    "A4": _card(210.0, 297.0, "A4 (A3 folded)", "210 x 297 mm card from an A3 sheet"),
    "A3": _card(297.0, 420.0, "A3 (A2 folded)", "297 x 420 mm card from an A2 sheet"),
    "HL": _card(5.5 * IN, 8.5 * IN, "Half Letter (Letter folded)",
                "5.5 x 8.5 in card from a US Letter sheet"),
    "LT": _card(8.5 * IN, 11 * IN, "Letter (Tabloid folded)",
                "8.5 x 11 in card from an 11 x 17 in sheet"),
    "A7": _card(5 * IN, 7 * IN, "5 x 7 in greeting card", "US A7 envelope card"),
    "SQ": _card(150.0, 150.0, "150 mm square", "150 mm square card"),
    "PB85": _card(8.5 * IN, 8.5 * IN, "Picture book 8.5 x 8.5 in",
                  "Square picture book, the most common trim"),
    "PB810": _card(8 * IN, 10 * IN, "Picture book 8 x 10 in (portrait)",
                   "Traditional portrait picture book"),
    "PB108": _card(10 * IN, 8 * IN, "Picture book 10 x 8 in (landscape)",
                   "Landscape picture book for wide scenes"),
    "PB75": _card(7.5 * IN, 7.5 * IN, "Picture book 7.5 x 7.5 in",
                  "Small square, board-book size"),
    "PB811": _card(8.5 * IN, 11 * IN, "Picture book 8.5 x 11 in",
                   "Large portrait, activity books"),
}


class Panel:
    def __init__(self, name, piece, kind, polys, asm, parent=None, hinge=None,
                 label=""):
        self.name = name
        self.piece = piece
        self.kind = kind  # "page", "panel", "tab"
        self.polys = [ccw(p) for p in polys if len(p) >= 3]
        self.asm = asm
        self.parent = parent
        self.hinge = hinge
        self.label = label or name
        self.outside = False  # lies behind the card (pull strips): skip fit checks
        self.free = False  # glued to nothing: its pose is tabulated, opening by opening
        self.zoff = 0.0  # mm the surface sits off its own fold lines (display only)
        self.lift = 0.0  # mm the rig raises it off its parent near flat (display only)
        self.lift_dir = None  # which way, in the parent's pattern (None: its normal)

    @property
    def glue(self):
        return self.kind == "tab"


class Hinge:
    """Fold between a panel and its parent.

    Rel(t) = asm_parent(t)^-1 @ asm_child(t) == Hp @ RotY(psi(t)) @ Fc^-1
    Hp: hinge frame in the parent's pattern; Fc: the same fold in the child's
    pattern (Y along the fold, Z the printed normal).
    """

    def __init__(self, Hp, Fc, kind="LINEAR", sph=None):
        self.Hp = Hp
        self.Fc = Fc
        self.kind = kind
        self.sph = sph or {}
        self.expr = None  # filled by Model.solve_hinges
        self.check = None


class Piece:
    def __init__(self, name, label, slot, anchor, is_card=False):
        self.name = name
        self.label = label
        self.slot = slot  # art tile index (stable per mechanism uid)
        self.anchor = anchor  # pattern point at the art tile centre
        self.is_card = is_card
        self.panels = []
        self.wrap = None  # walls an image wraps round (x0, y0, x1, y1), if any


def halfplanes(poly):
    """Inside half-planes (n, d) of a convex CCW polygon: n . p >= d."""
    out = []
    for i in range(len(poly)):
        a, b = poly[i], poly[(i + 1) % len(poly)]
        n = (-(b[1] - a[1]), b[0] - a[0])
        out.append((n, n[0] * a[0] + n[1] * a[1]))
    return out


def split_convex(poly, hps, eps=1e-6):
    """Split a convex polygon by a convex region: (outside parts, inside part)."""
    outs, rem = [], list(poly)
    for n, d in hps:
        o = clip_halfplane(rem, (-n[0], -n[1]), -d)
        if len(o) >= 3 and abs(poly_area(o)) > eps:
            outs.append(o)
        rem = clip_halfplane(rem, n, d)
        if len(rem) < 3:
            return outs, []
    if abs(poly_area(rem)) <= eps:
        return outs, []
    return outs, [rem]


def poly_area(poly):
    a = 0.0
    for i in range(len(poly)):
        x0, y0 = poly[i]
        x1, y1 = poly[(i + 1) % len(poly)]
        a += x0 * y1 - x1 * y0
    return 0.5 * a


def unit2(x, y):
    n = math.hypot(x, y)
    return (x / n, y / n)


class Host:
    """A fold a mechanism can sit on: two panels (p1 on the left, p2 on the
    right) meeting along a line parallel to the spine. The fold sits at
    pattern x = x1 in p1 and x = x2 in p2, and pattern y = card y - y1 (y2).

    Its "virtual pages" L(t), R(t) map a spine-style pattern (fold at x = 0,
    y = card height, left page at x < 0) onto the two panels, so every
    mechanism can be written as if it sat on the card spine."""

    def __init__(self, model, p1, x1, y1, p2, x2, y2, label, T1=None, T2=None):
        self.m = model
        self.p1, self.x1, self.y1 = p1, x1, y1
        self.p2, self.x2, self.y2 = p2, x2, y2
        self.label = label
        # virtual (spine-style) pattern -> each panel's own pattern; any rigid
        # placement, so a fold needn't run along the panels' pattern Y
        self.T1 = T1 if T1 is not None else Matrix.Translation((x1, -y1, 0.0))
        self.T2 = T2 if T2 is not None else Matrix.Translation((x2, -y2, 0.0))
        self.lift = (1.0, 1.0)
        self.trig = True  # panels turn with the card's own angle (closed forms apply)
        self.open_max = None  # a stage set's halves open only so far
        self.size = None  # (half width, height) of a stage set's background
        self.key = None

    @property
    def cut_ok(self):
        P = self.m.panels
        return (P[self.p1].piece == P[self.p2].piece and
                all(abs(self.T1[i][j] - self.T2[i][j]) < 1e-6 for i in range(3) for j in range(4)))

    def v1(self, x, y):
        """Virtual point -> p1's pattern."""
        return (self.T1 @ Vector((x, y, 0.0))).to_2d()[:]

    def d1(self, x, y):
        """Virtual direction -> p1's pattern."""
        return (self.T1.to_3x3() @ Vector((x, y, 0.0))).to_2d()[:]

    @property
    def is_spine(self):
        return self.p1 == "Page.L" and self.p2 == "Page.R" and self.T1 == Matrix.Identity(4)

    def L(self, t):
        return self.m.panels[self.p1].asm(t) @ self.T1

    def R(self, t):
        return self.m.panels[self.p2].asm(t) @ self.T2

    def dirs(self, t):
        # asked for many times at the same opening while hinges are sampled
        # (everything standing on this fold): remember them
        c = self.__dict__.setdefault("_dirs", {})
        v = c.get(t)
        if v is None:
            L, R = self.L(t), self.R(t)
            Lr, Rr = L.to_3x3(), R.to_3x3()
            v = (L.to_translation(), Lr @ Vector((-1, 0, 0)), Rr @ Vector((1, 0, 0)),
                 Lr @ Vector((0, 1, 0)), Lr @ Z, Rr @ Z)
            if len(c) > 8192:
                c.clear()
            c[t] = v
        return tuple(x.copy() for x in v)

    def finish(self):
        """Which way glued tabs lift off each panel (towards the mechanism)."""
        S, l, r, Y, nl, nr = self.dirs(self.m.t_ref)
        self.lift = (1.0 if nl.dot(r) >= 0 else -1.0, 1.0 if nr.dot(l) >= 0 else -1.0)
        return self
