"""Pop-up card kinematics.

The card lies in its flat *pattern* space: spine along +Y from y = 0 to H,
left page at x in [-W, 0], right page at x in [0, W], printed (inside) face
towards +Z. The open angle t runs 0 (closed) to 180 degrees (flat).

Every panel has
  * polys      flat pattern polygons (mm, in its piece's pattern space)
  * asm(t)     4x4 matrix: pattern space -> assembled card space at angle t
  * parent     the panel it hangs from in the rig (None for the two pages)
  * hinge      fold it turns about relative to its parent, or None when it is
               glued (fixed) to its parent

Hinges are either LINEAR (the fold angle changes linearly with t: pages and
box folds) or SPHERICAL (V-folds: four fold lines through one point). For
both, `hinge_expression` returns a Blender driver expression in `t` (degrees)
that uses only functions Blender's simple-expression evaluator understands,
so the rig works without enabling Python scripts.
"""

import math

from mathutils import Matrix, Vector

from .geom import (Z, angle_from_roty, ccw, clip_halfplane, frame, hinge_frame_2d,
                   is_roty, rot_y, v3)

T_MIN = 0.05  # degrees; avoids the degenerate fully-closed pose
TAB_LIFT = 0.15  # mm a glued tab floats above the page (avoids z-fighting)
SAMPLES = [0.5, 5, 15, 30, 45, 60, 75, 90, 105, 120, 135, 150, 165, 180]

IN = 25.4


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

    def __init__(self, model, p1, x1, y1, p2, x2, y2, label):
        self.m = model
        self.p1, self.x1, self.y1 = p1, x1, y1
        self.p2, self.x2, self.y2 = p2, x2, y2
        self.label = label
        self.T1 = Matrix.Translation((x1, -y1, 0.0))
        self.T2 = Matrix.Translation((x2, -y2, 0.0))
        self.lift = (1.0, 1.0)

    @property
    def cut_ok(self):
        P = self.m.panels
        return (P[self.p1].piece == P[self.p2].piece and abs(self.x1 - self.x2) < 1e-6
                and abs(self.y1 - self.y2) < 1e-6)

    @property
    def is_spine(self):
        return self.p1 == "Page.L" and self.p2 == "Page.R" and self.x1 == 0.0

    def L(self, t):
        return self.m.panels[self.p1].asm(t) @ self.T1

    def R(self, t):
        return self.m.panels[self.p2].asm(t) @ self.T2

    def dirs(self, t):
        L, R = self.L(t), self.R(t)
        Lr, Rr = L.to_3x3(), R.to_3x3()
        return (L.to_translation(), Lr @ Vector((-1, 0, 0)), Rr @ Vector((1, 0, 0)),
                Lr @ Vector((0, 1, 0)), Lr @ Z, Rr @ Z)

    def finish(self):
        """Which way glued tabs lift off each panel (towards the mechanism)."""
        S, l, r, Y, nl, nr = self.dirs(90.0)
        self.lift = (1.0 if nl.dot(r) >= 0 else -1.0, 1.0 if nr.dot(l) >= 0 else -1.0)
        return self


class Model:
    def __init__(self, card, mechs):
        self.card = dict(card)
        self.W = float(card["W"])
        self.H = float(card["H"])
        self.hold = card.get("hold", "RIGHT")
        self.panels = {}
        self.pieces = {}
        self.order = []  # panel names, parents before children
        self.warnings = []
        self.mechs = [dict(m) for m in mechs]
        self._branch = {}
        self.joints = {}
        self.hosts = {}
        self.cut_panels = set()
        self._build()
        self.solve_hinges()

    # ----------------------------------------------------------------- pages
    def gammas(self, t):
        """Rotation of the left and right page about the spine (radians)."""
        b = math.radians(180.0 - t)
        if self.hold == "SYM":
            return 0.5 * b, 0.5 * b
        if self.hold == "LEFT":
            return 0.0, b
        return b, 0.0  # RIGHT page stays flat

    def page_asm(self, side):
        if side == "L":
            return lambda t: rot_y(self.gammas(t)[0])
        return lambda t: rot_y(-self.gammas(t)[1])

    # ------------------------------------------------------------ add things
    def add_piece(self, piece):
        self.pieces[piece.name] = piece
        return piece

    def add(self, panel):
        if not panel.polys:
            return None
        self.panels[panel.name] = panel
        self.pieces[panel.piece].panels.append(panel.name)
        self.order.append(panel.name)
        return panel

    def warn(self, msg):
        if msg not in self.warnings:
            self.warnings.append(msg)

    def carve(self, piece, region, allowed, lab):
        """Cut a convex region (pattern coords) out of a piece's panels.
        Returns the cut-out cells, or None (with a warning) if the region
        is not wholly on the allowed panels."""
        region = ccw(region)
        hps = halfplanes(region)
        want = poly_area(region)
        keep, got, total = {}, {}, 0.0
        for name in self.pieces[piece].panels:
            p = self.panels[name]
            outs, ins = [], []
            for poly in p.polys:
                o, i = split_convex(poly, hps)
                outs += o
                ins += i
            if ins and name not in allowed:
                self.warn(f"{lab}: overlaps {p.label.split(':')[0]}; skipped")
                return None
            keep[name], got[name] = outs, ins
            total += sum(poly_area(q) for q in ins)
        if abs(total - want) > max(0.5, 0.002 * want):
            self.warn(f"{lab}: does not fit on what it is cut from; skipped")
            return None
        for name, outs in keep.items():
            if got[name]:
                self.panels[name].polys = [ccw(q) for q in outs]
        return [q for qs in got.values() for q in qs]

    @staticmethod
    def split_cells(cells, n, d):
        """Cells on each side of a line: (n . p >= d, n . p <= d)."""
        a, b = [], []
        for c in cells:
            p = clip_halfplane(c, n, d)
            q = clip_halfplane(c, (-n[0], -n[1]), -d)
            if len(p) >= 3 and abs(poly_area(p)) > 1e-6:
                a.append(p)
            if len(q) >= 3 and abs(poly_area(q)) > 1e-6:
                b.append(q)
        return a, b

    # ----------------------------------------------------------------- build
    def _build(self):
        W, H = self.W, self.H
        card = self.add_piece(Piece("Card", "Card", 0, (0.0, H / 2), True))
        card.size = (2 * W, H)
        self.add(Panel("Page.L", "Card", "page", [[(-W, 0), (0, 0), (0, H), (-W, H)]],
                       self.page_asm("L"), None,
                       Hinge(Matrix.Identity(4), Matrix.Identity(4)), "Left page"))
        self.add(Panel("Page.R", "Card", "page", [[(0, 0), (W, 0), (W, H), (0, H)]],
                       self.page_asm("R"), None,
                       Hinge(Matrix.Identity(4), Matrix.Identity(4)), "Right page"))
        self.hosts[(0, "S")] = Host(self, "Page.L", 0.0, 0.0, "Page.R", 0.0, 0.0,
                                    "Card spine").finish()

        # parents (hosts) before children; drop cycles and missing hosts
        by_uid = {m["uid"]: m for m in self.mechs}
        order, state = [], {}

        def visit(m):
            st = state.get(m["uid"])
            if st == 2:
                return True
            if st == 1:
                return False
            state[m["uid"]] = 1
            h = m.get("host", 0)
            ok = True
            if h:
                parent = by_uid.get(h)
                if parent is None or parent["type"] != "BOX":
                    self.warn(f"{m['label']}: its host box is missing; skipped")
                    ok = False
                elif not visit(parent):
                    self.warn(f"{m['label']}: hosts form a loop; skipped")
                    ok = False
            state[m["uid"]] = 2
            if ok:
                order.append(m)
            else:
                m["_skip"] = True
            return ok

        for m in self.mechs:
            visit(m)
        for m in order:
            h = m.get("host", 0)
            host = self.hosts.get((h, m.get("fold", "A")) if h else (0, "S"))
            if host is None:
                self.warn(f"{m['label']}: its host was skipped; skipped too")
                continue
            if m["type"] == "VFOLD":
                self._vfold(m, host)
            elif m["type"] == "MOUTH":
                self._mouth(m, host)
            elif m["type"] == "BOX":
                self._box(m, host)

    # ------------------------------------------------------- page directions
    def dirs(self, t):
        L, R = self.panels["Page.L"].asm(t), self.panels["Page.R"].asm(t)
        l = L.to_3x3() @ Vector((-1, 0, 0))
        r = R.to_3x3() @ Vector((1, 0, 0))
        return l, r, L.to_3x3() @ Z, R.to_3x3() @ Z

    # -------------------------------------------------------------- box fold
    def _box(self, m, host):
        """Parallel fold on a host fold. A on the host's left panel at distance
        a (height) from the fold, B on its right panel at distance b (depth).
        Panel AC stays parallel to the right panel and CB to the left, so
        S-A-C-B is a parallelogram."""
        uid = m["uid"]
        a, b = float(m["height"]), float(m["depth"])
        y0, w = float(m["y"]), float(m["width"])
        lab = m["label"]
        W, H = self.W, self.H
        if host.is_spine and a + b > W + 1e-6:
            self.warn(f"{lab}: height + depth ({a + b:.0f} mm) is deeper than the "
                      f"page ({W:.0f} mm), so it sticks out when closed")
        if y0 < -1e-6 or y0 + w > H + 1e-6:
            self.warn(f"{lab}: runs past the top or bottom of the card")
        base = f"Box{uid}"
        role = "inset" if m.get("fold") == "C" and m.get("host") else ""
        lift1, lift2 = host.lift

        if m.get("style") == "CUT":  # cut into the host's paper (box layer)
            if not host.cut_ok:
                self.warn(f"{lab}: a box layer must be cut across one fold of one "
                          f"piece of paper (use a glued box here); skipped")
                return
            piece = self.panels[host.p1].piece
            x1, yo = host.x1, host.y1
            Y0 = y0 - yo
            rect = [(x1 - a, Y0), (x1 + b, Y0), (x1 + b, Y0 + w), (x1 - a, Y0 + w)]
            cells = self.carve(piece, rect, {host.p1, host.p2}, lab)
            if cells is None:
                return
            xc = x1 + b - a
            cb_cells, ac_cells = self.split_cells(cells, (1.0, 0.0), xc)
            Tv = Matrix.Translation((-x1, yo, 0.0))  # pattern -> virtual

            def asm_ac(t):
                S, l, r, Y, nl, nr = host.dirs(t)
                return frame(S + a * l + a * r, r, Y) @ Tv

            def asm_cb(t):
                S, l, r, Y, nl, nr = host.dirs(t)
                return frame(S + b * r + b * l, -l, Y) @ Tv

            hA = hinge_frame_2d((x1 - a, Y0), (0, 1))
            hC = hinge_frame_2d((xc, Y0), (0, 1))
            ac = self.add(Panel(f"{base}.AC", piece, "panel", ac_cells, asm_ac, host.p1,
                                Hinge(hA, hA), f"{lab}: top"))
            cb = self.add(Panel(f"{base}.CB", piece, "panel", cb_cells, asm_cb,
                                ac.name if ac else host.p1,
                                Hinge(hC, hC) if ac else Hinge(hA, hA), f"{lab}: front"))
            if not (ac and cb):
                self.warn(f"{lab}: height or depth is too small to fold")
                return
            self.cut_panels |= {ac.name, cb.name}
            xs = dict(A=x1 - a, C=xc, B=x1 + b, y=yo)
        else:
            # Glued strip: tabA | AC (b) | CB (a) | tabB along u, width w along v
            t_ = min(float(m.get("tab", 12.0)), a, b)
            if float(m.get("tab", 12.0)) > min(a, b) + 1e-6:
                self.warn(f"{lab}: glue tabs shortened to {t_:.0f} mm to stay hidden")
            piece = f"Box{uid}"
            self.add_piece(Piece(piece, lab, 1 + uid, (0.0, w / 2)))
            ch = min(0.3 * t_, 0.25 * w)
            poly_tabA = [(-t_, ch), (0, 0), (0, w), (-t_, w - ch)]
            poly_ac = [(0, 0), (b, 0), (b, w), (0, w)]
            poly_cb = [(b, 0), (a + b, 0), (a + b, w), (b, w)]
            poly_tabB = [(a + b, 0), (a + b + t_, ch), (a + b + t_, w - ch), (a + b, w)]

            def asm_tabA(t):
                S, l, r, Y, nl, nr = host.dirs(t)
                return frame(S + a * l + y0 * Y + lift1 * TAB_LIFT * nl, l, Y)

            def asm_ac(t):
                S, l, r, Y, nl, nr = host.dirs(t)
                return frame(S + a * l + y0 * Y, r, Y)

            def asm_cb(t):
                S, l, r, Y, nl, nr = host.dirs(t)
                return frame(S + (a + b) * l + b * r + y0 * Y, -l, Y)

            def asm_tabB(t):
                S, l, r, Y, nl, nr = host.dirs(t)
                return frame(S + (a + 2 * b) * r + y0 * Y + lift2 * TAB_LIFT * nr, -r, Y)

            self.add(Panel(f"{base}.TabA", piece, "tab", [poly_tabA], asm_tabA,
                           host.p1, None, f"{lab}: tab A"))
            ac = self.add(Panel(f"{base}.AC", piece, "panel", [poly_ac], asm_ac, host.p1,
                                Hinge(hinge_frame_2d((host.x1 - a, y0 - host.y1), (0, 1)),
                                      hinge_frame_2d((0, 0), (0, 1))),
                                f"{lab}: top"))
            self.add(Panel(f"{base}.CB", piece, "panel", [poly_cb], asm_cb, ac.name,
                           Hinge(hinge_frame_2d((b, 0), (0, 1)),
                                 hinge_frame_2d((b, 0), (0, 1))),
                           f"{lab}: front"))
            self.add(Panel(f"{base}.TabB", piece, "tab", [poly_tabB], asm_tabB,
                           host.p2, None, f"{lab}: tab B"))
            xs = dict(A=0.0, C=b, B=a + b, y=y0)
        if role:
            for n in (f"{base}.AC", f"{base}.CB"):
                if n in self.panels:
                    self.panels[n].label = self.panels[n].label.replace(": ", " (inset): ")
        AC, CB, yo = f"{base}.AC", f"{base}.CB", xs["y"]
        self.hosts[(uid, "A")] = Host(self, host.p1, host.x1 - a, host.y1, AC, xs["A"], yo,
                                      f"{lab}: on top").finish()
        self.hosts[(uid, "C")] = Host(self, AC, xs["C"], yo, CB, xs["C"], yo,
                                      f"{lab}: inset").finish()
        self.hosts[(uid, "B")] = Host(self, CB, xs["B"], yo, host.p2, host.x2 + b, host.y2,
                                      f"{lab}: in front").finish()

    # ---------------------------------------------------------------- V-fold
    def _crease_parts(self, J, t):
        t = max(t, T_MIN)
        host = J["host"]
        L, R = host.L(t), host.R(t)
        Lr, Rr = L.to_3x3(), R.to_3x3()
        uL = Lr @ Vector((J["uL"][0], J["uL"][1], 0))
        uR = Rr @ Vector((J["uR"][0], J["uR"][1], 0))
        nl, nr = Lr @ Z, Rr @ Z
        cl, cr = math.cos(J["aL"]), math.cos(J["aR"])
        G = uL.dot(uR)
        det = max(1.0 - G * G, 1e-12)
        ka = (cl - G * cr) / det
        kb = (cr - G * cl) / det
        base = ka * uL + kb * uR
        k2 = 1.0 - base.length_squared
        n = uL.cross(uR)
        if n.length < 1e-9:
            n = nl.copy()
        n.normalize()
        P3 = L @ Vector((0.0, J["y"], 0.0))
        return base, math.sqrt(max(k2, 0.0)), n, nl, nr, uL, uR, k2 > -1e-6, P3

    def crease(self, key, t):
        """Crease direction of a V joint (two fold lines through one point on a
        host fold, each half making a fixed angle with the crease).

        Two creases satisfy the angles; the paper stays on the branch that
        reaches into the gap between the host panels."""
        J = self.joints[key]
        sgn = self._branch.get(key)
        if sgn is None:
            base, k, n, nl, nr, *_ = self._crease_parts(J, 90.0)
            sgn = max((1.0, -1.0), key=lambda s: (base + s * k * n).normalized().dot(nl + nr))
            self._branch[key] = sgn
        base, k, n, nl, nr, uL, uR, ok, P3 = self._crease_parts(J, t)
        return (base + sgn * k * n).normalized(), uL, uR, ok, P3

    def vfold_crease(self, m, t):
        """Back-compatible: crease of a V-fold mechanism dict."""
        c, uL, uR, ok, _ = self.crease(f"VFold{m['uid']}", t)
        return c, uL, uR, ok

    def _half(self, name, piece, polys, Ppat, gpiece, cpat, side, key, label):
        """One rigid half of a V joint. gpiece/cpat: glue line and crease
        directions from the V point in the half's own pattern."""
        J = self.joints[key]
        host = J["host"]
        L = side == "L"
        alpha, alpha_o = (J["aL"], J["aR"]) if L else (J["aR"], J["aL"])
        sa, ca = math.sin(alpha), math.cos(alpha)
        xp = (gpiece[1], -gpiece[0])
        sg = 1.0 if xp[0] * cpat[0] + xp[1] * cpat[1] > 0 else -1.0
        Fc = hinge_frame_2d(Ppat, gpiece)
        Fci = Fc.inverted()
        parent, px, py, g_page = ((host.p1, host.x1, host.y1, J["uL"]) if L
                                  else (host.p2, host.x2, host.y2, J["uR"]))
        Hp = hinge_frame_2d((px, J["y"] - py), g_page)

        def asm(t):
            c, uL, uR, ok, P3 = self.crease(key, t)
            u = uL if L else uR
            e = sg * (c - ca * u) / sa
            return frame(P3, e, u) @ Fci

        other = host.p2 if L else host.p1
        uo = J["uR"] if L else J["uL"]
        return self.add(Panel(name, piece, "panel", polys, asm, parent,
                              Hinge(Hp, Fc, "SPHERICAL",
                                    dict(key=key, alpha=alpha, alpha_o=alpha_o, sigma=sg,
                                         other=other, uo=uo)),
                              label))

    def _vfold(self, m, host):
        uid = m["uid"]
        lab = m["label"]
        H = self.H
        yP = float(m["y"])
        phl, phr = math.radians(m["phi_l"]), math.radians(m["phi_r"])
        all_, alr = math.radians(m["alpha_l"]), math.radians(m["alpha_r"])
        g, Lc, t_ = float(m["glue"]), float(m["height"]), float(m["tab"])
        base = f"VFold{uid}"
        piece = base
        if math.sin(all_) < 1e-3 or math.sin(alr) < 1e-3:
            self.warn(f"{lab}: piece angle must be between 0 and 180 degrees")
            return
        # art tile: the V point sits low in the tile, the halves rise above it
        self.add_piece(Piece(piece, lab, 1 + uid, (0.0, 0.3 * 297.0)))
        if not (0 <= yP <= H):
            self.warn(f"{lab}: the V point is off the card")

        uLf = (-math.sin(phl), math.cos(phl))
        uRf = (math.sin(phr), math.cos(phr))
        uLp = (-math.sin(all_), math.cos(all_))
        uRp = (math.sin(alr), math.cos(alr))
        self.joints[base] = dict(host=host, y=yP, uL=uLf, uR=uRf, aL=all_, aR=alr)

        # Pattern: crease along +Y' from P' = (0, 0); halves either side.
        GL = (g * uLp[0], g * uLp[1])
        GR = (g * uRp[0], g * uRp[1])
        Q = (0.0, Lc)
        if m.get("shape") == "TRI":  # beak: two triangles meeting at a point
            halfL = [(0, 0), Q, GL]
            halfR = [(0, 0), GR, Q]
        else:
            halfL = [(0, 0), Q, (GL[0], GL[1] + Lc), GL]
            halfR = [(0, 0), GR, (GR[0], GR[1] + Lc), Q]
        FcL = hinge_frame_2d((0, 0), uLp)
        FcR = hinge_frame_2d((0, 0), uRp)

        # Tabs: fold flat onto the host along the glue line, inside or outside
        bis = Vector((uLf[0] + uRf[0], uLf[1] + uRf[1], 0))
        if bis.length < 1e-6:
            bis = Vector((0, 1, 0))
        inside = m.get("tab_side", "IN") == "IN"
        tabs = []
        for side, uf, up, Fc, sigma in (("L", uLf, uLp, FcL, 1.0), ("R", uRf, uRp, FcR, -1.0)):
            Xc = Vector((up[1], -up[0], 0))  # pattern X of the hinge frame
            s2 = -sigma * Xc  # tab side in the pattern (away from the half)
            q = Vector((uf[1], -uf[0], 0))
            if (q.dot(bis) > 0) != inside:
                q = -q
            lift = host.lift[0 if side == "L" else 1]
            # Tab pattern -> virtual page: Y'(up) -> uf, X' -> -sigma * q
            T = frame(Vector((0, yP, lift * TAB_LIFT)), -sigma * q,
                      Vector((uf[0], uf[1], 0))) @ Fc.inverted()
            gp = (g * up[0], g * up[1])
            ins = min(0.5 * t_, 0.3 * g)
            poly = [(0, 0), gp,
                    (gp[0] + t_ * s2.x - ins * up[0], gp[1] + t_ * s2.y - ins * up[1]),
                    (t_ * s2.x, t_ * s2.y)]
            # stay on this side of the fold: virtual x <= -gap (left), >= gap (right)
            sgn = -1.0 if side == "L" else 1.0
            n2 = (sgn * T[0][0], sgn * T[0][1])
            poly = clip_halfplane(poly, n2, 0.5 - sgn * T[0][3])
            tabs.append([side, poly, T, s2 + 0.5 * Vector((up[0], up[1], 0))])
        # keep the two tabs apart where they meet at the V point
        sep = tabs[0][3] - tabs[1][3]
        if sep.length > 1e-6:
            sep.normalize()
            tabs[0][1] = clip_halfplane(tabs[0][1], (sep.x, sep.y), 0.4)
            tabs[1][1] = clip_halfplane(tabs[1][1], (-sep.x, -sep.y), 0.4)

        self._half(f"{base}.HalfL", piece, [halfL], (0, 0), uLp, (0, 1), "L", base,
                   f"{lab}: left half")
        self._half(f"{base}.HalfR", piece, [halfR], (0, 0), uRp, (0, 1), "R", base,
                   f"{lab}: right half")
        for side, poly, T, _ in tabs:
            parent, Tp = (host.p1, host.T1) if side == "L" else (host.p2, host.T2)
            pa = self.panels[parent].asm
            Tpat = Tp @ T
            self.add(Panel(f"{base}.Tab{side}", piece, "tab", [poly],
                           (lambda t, pa=pa, T=Tpat: pa(t) @ T), parent, None,
                           f"{lab}: tab {side}"))

        tears = [s for s in SAMPLES if not self.crease(base, s)[3]]
        if tears:
            self.warn(f"{lab}: tears if opened past {min(tears):.0f} degrees (make the "
                      f"piece angle at least the glue angle)")

    # ----------------------------------------------------------------- mouth
    def _mouth(self, m, host):
        """Pop-up mouth cut into the paper: a slit across the fold and two
        pairs of triangles (upper and lower jaw) that fold out as the card
        opens. Each jaw is a V joint whose halves are cut from the host."""
        uid, lab = m["uid"], m["label"]
        y0 = float(m["y"])
        Lj, a, b = float(m["jaw"]), float(m["upper"]), float(m["lower"])
        if not host.cut_ok:
            self.warn(f"{lab}: a mouth must be cut across one fold of one piece of "
                      f"paper; skipped")
            return
        piece = self.panels[host.p1].piece
        x1, yo = host.x1, host.y1
        Y0 = y0 - yo
        left = self.carve(piece, [(x1, Y0 - b), (x1, Y0 + a), (x1 - Lj, Y0)],
                          {host.p1}, lab)
        if left is None:
            return
        right = self.carve(piece, [(x1, Y0 - b), (x1 + Lj, Y0), (x1, Y0 + a)],
                           {host.p2}, lab)
        if right is None:
            self.warn(f"{lab}: the right half does not fit; the cut is incomplete")
            return
        ul, ll = self.split_cells(left, (0.0, 1.0), Y0)
        ur, lr = self.split_cells(right, (0.0, 1.0), Y0)
        base = f"Mouth{uid}"
        for jaw, yP, gL, gR, cp, cl, cr, name in (
            ("U", y0 + a, unit2(-Lj, -a), unit2(Lj, -a), (0, -1), ul, ur, "upper jaw"),
            ("D", y0 - b, unit2(-Lj, b), unit2(Lj, b), (0, 1), ll, lr, "lower jaw"),
        ):
            key = f"{base}.{jaw}"
            alpha = math.acos(max(-1.0, min(1.0, gL[0] * cp[0] + gL[1] * cp[1])))
            self.joints[key] = dict(host=host, y=yP, uL=gL, uR=gR, aL=alpha, aR=alpha)
            P = (x1, yP - yo)
            self._half(f"{key}L", piece, cl, P, gL, cp, "L", key, f"{lab}: {name} left")
            self._half(f"{key}R", piece, cr, P, gR, cp, "R", key, f"{lab}: {name} right")
            self.cut_panels |= {f"{key}L", f"{key}R"}

    # ---------------------------------------------------------------- hinges
    def rel(self, name, t):
        p = self.panels[name]
        if p.parent is None:
            return p.asm(t)
        return self.panels[p.parent].asm(t).inverted() @ p.asm(t)

    def true_psi(self, name, t):
        p = self.panels[name]
        h = p.hinge
        M = h.Hp.inverted() @ self.rel(name, t) @ h.Fc
        if not is_roty(M, 1e-4):
            raise ValueError(f"{name}: fold is not a pure hinge at t={t}")
        return angle_from_roty(M)

    def solve_hinges(self):
        for name in self.order:
            p = self.panels[name]
            h = p.hinge
            if h is None:
                continue
            if h.kind == "LINEAR":
                p90, p1 = self.true_psi(name, 90.0), self.true_psi(name, 180.0)
                d = (p1 - p90 + math.pi) % (2 * math.pi) - math.pi
                k1 = round(d / (0.5 * math.pi) * 2) / 2.0  # moves 1:1 or 1:2
                k0 = p1 - k1 * math.pi
                h.expr = f"{k0:.9g}{k1:+.9g}*radians(t)" if abs(k1) > 1e-12 else f"{k0:.9g}"
                h.fn = lambda t, k0=k0, k1=k1: k0 + k1 * math.radians(t)
            else:
                self._spherical(name, p, h)
            err = 0.0
            for s in self._valid_samples(p):
                d = h.fn(s) - self.true_psi(name, s)
                d = (d + math.pi) % (2 * math.pi) - math.pi
                err = max(err, abs(d))
            h.check = err
            if err > 2e-3:  # 0.002 rad: under 0.1 mm on a 50 mm panel
                raise ValueError(f"{name}: driver formula is off by {err:.2e} rad")

    def _valid_samples(self, p):
        """Angles where the paper can actually follow (no tearing)."""
        if p.hinge.kind != "SPHERICAL":
            return SAMPLES
        key = p.hinge.sph["key"]
        return [s for s in SAMPLES if self.crease(key, s)[3]]

    def _spherical(self, name, p, h):
        sph = h.sph
        parent = self.panels[p.parent]
        other = self.panels[sph["other"]]
        uo = Vector((sph["uo"][0], sph["uo"][1], 0))
        Xp, Yp, Zp = (h.Hp.to_3x3().col[i] for i in range(3))

        def dots(t):
            u = parent.asm(t).to_3x3().inverted() @ (other.asm(t).to_3x3() @ uo)
            return Xp.dot(u), Yp.dot(u), Zp.dot(u)

        # each dot product is k0 + k1*cos(t) + k2*sin(t) exactly
        f0, f90, f180 = dots(0.0), dots(90.0), dots(180.0)
        co = []
        for i in range(3):
            k0 = 0.5 * (f0[i] + f180[i])
            k1 = 0.5 * (f0[i] - f180[i])
            k2 = f90[i] - k0
            co.append((k0, k1, k2))
        al, ao, sg = sph["alpha"], sph["alpha_o"], sph["sigma"]
        sa, ca = math.sin(al), math.cos(al)
        A = tuple(sg * sa * k for k in co[0])
        B = tuple(-sg * sa * k for k in co[2])
        D = (math.cos(ao) - ca * co[1][0], -ca * co[1][1], -ca * co[1][2])

        def ev(c, t):
            r = math.radians(max(t, T_MIN))
            return c[0] + c[1] * math.cos(r) + c[2] * math.sin(r)

        def psi(t, s):
            a_, b_, d_ = ev(A, t), ev(B, t), ev(D, t)
            rr = max(math.sqrt(a_ * a_ + b_ * b_), 1e-9)
            return math.atan2(b_, a_) + s * math.acos(max(-1.0, min(1.0, d_ / rr)))

        ok = self._valid_samples(p) or [180.0]
        t_ref = min(ok, key=lambda x: abs(x - 90.0))
        ref = self.true_psi(name, t_ref)
        s = min((1.0, -1.0), key=lambda s: abs(
            (psi(t_ref, s) - ref + math.pi) % (2 * math.pi) - math.pi))

        # Blender limits driver expressions to 256 characters, so the three
        # linear terms are driven separately (see build.py) and combined here.
        h.parts = dict(A=A, B=B, D=D, s=s)
        sgn = "+" if s > 0 else "-"
        h.expr = f"atan2(b,a){sgn}acos(max(-1,min(1,d/max(sqrt(a*a+b*b),1e-9))))"
        h.fn = lambda t, s=s: psi(t, s)

    # --------------------------------------------------------- closing stop
    def close_angle(self, thickness, clearance=0.1, near_spine=8.0, cap=45.0):
        """Smallest open angle (degrees) at which everything folded inside the
        closed card fits between the pages, given the paper thickness (mm).

        Each mechanism panel's closed footprint is mapped onto the page
        (distance from the spine, height); where n layers stack at distance
        u from the spine the pages must be 2 u sin(t/2) >= n * thickness
        apart. Within near_spine of the spine the paper bends instead, so
        those points are ignored."""
        t0 = 0.5
        l, r, nl, nr = self.dirs(t0)
        e = (l + r).normalized()
        foot = []
        for name in self.order:
            p = self.panels[name]
            if p.kind == "page":
                continue
            M = p.asm(t0)
            for poly in p.polys:
                q = [M @ v3(c) for c in poly]
                foot.append([(w.dot(e), w.y) for w in q])
        if not foot:
            return 0.0

        def inside(pt, poly):
            sgn = 0
            for i in range(len(poly)):
                a, b = poly[i], poly[(i + 1) % len(poly)]
                cr = (b[0] - a[0]) * (pt[1] - a[1]) - (b[1] - a[1]) * (pt[0] - a[0])
                if abs(cr) < 1e-9:
                    continue
                s_ = 1 if cr > 0 else -1
                if sgn and s_ != sgn:
                    return False
                sgn = s_
            return True

        need = 0.0
        for poly in foot:
            cx = sum(c[0] for c in poly) / len(poly)
            cy = sum(c[1] for c in poly) / len(poly)
            pts = [(cx, cy)] + [(cx + 0.95 * (c[0] - cx), cy + 0.95 * (c[1] - cy)) for c in poly]
            for pt in pts:
                u = pt[0]
                if u < near_spine:
                    continue
                n = sum(1 for f in foot if inside(pt, f))
                ang = 2 * math.degrees(math.asin(min(1.0, (n * thickness + clearance) / (2 * u))))
                need = max(need, ang)
        return min(need, cap)

    # ------------------------------------------------------------- checks
    @staticmethod
    def _overlap(a, b):
        r = list(a)
        for n, d in halfplanes(ccw(b)):
            r = clip_halfplane(r, n, d)
            if len(r) < 3:
                return 0.0
        return abs(poly_area(r))

    def check_overlaps(self):
        """Glue tabs and cut-outs that land on the same paper must not overlap
        each other, and tabs must land on paper (not on a hole)."""
        prints = {}  # piece -> [(mechanism label, kind, convex poly in pattern)]
        for name in self.order:
            p = self.panels[name]
            lab = p.label.split(":")[0].replace(" (inset)", "")
            if p.kind == "tab":
                host = self.panels[p.parent]
                M = host.asm(90.0).inverted() @ p.asm(90.0)
                for poly in p.polys:
                    q = [(M @ v3(c)).to_2d()[:] for c in poly]
                    prints.setdefault(host.piece, []).append((lab, "tab", q, host))
            elif name in self.cut_panels:
                for poly in p.polys:
                    prints.setdefault(p.piece, []).append((lab, "cut", poly, None))
        for piece, items in prints.items():
            for i, (la, ka, pa, ha) in enumerate(items):
                if ka == "tab":
                    on = sum(self._overlap(pa, q) for q in ha.polys)
                    if on < abs(poly_area(pa)) - 1.0:
                        self.warn(f"{la}: a glue tab hangs off {ha.label.split(':')[0]}")
                for lb, kb, pb, _ in items[i + 1:]:
                    if la != lb and self._overlap(pa, pb) > 1.0:
                        self.warn(f"{la} and {lb} overlap on the paper")

    def check_fit(self):
        """Panels must stay between the pages and inside the card outline."""
        self.check_overlaps()
        W, H = self.W, self.H
        for name in self.order:
            p = self.panels[name]
            if p.kind != "panel":
                continue
            lab = p.label.split(":")[0]
            pts = [v3(q) for poly in p.polys for q in poly]
            poke = None
            for t in SAMPLES:
                M = p.asm(t)
                l, r, nl, nr = self.dirs(t)
                for q in pts:
                    w = M @ q
                    if w.dot(nl) < -0.5 or w.dot(nr) < -0.5:
                        poke = t if poke is None else max(poke, t)
                        break
            if poke is not None:
                self.warn(f"{lab}: pokes through the card around {poke:.0f} degrees")
            M = p.asm(0.5)
            l, r, nl, nr = self.dirs(0.5)
            for q in pts:
                w = M @ q
                if w.y < -0.5 or w.y > H + 0.5 or max(w.dot(l), w.dot(r)) > W + 0.5:
                    self.warn(f"{lab}: sticks out of the card when closed")
                    break
