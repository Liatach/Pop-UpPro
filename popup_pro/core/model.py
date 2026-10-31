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

from .geom import (Z, angle_from_roty, ccw, clean, clip_halfplane, frame, hinge_frame_2d,
                   is_roty, rot_y, v3)

T_MIN = 0.05  # degrees; avoids the degenerate fully-closed pose
TAB_LIFT = 0.15  # mm a glued tab floats above the page (avoids z-fighting)
SAMPLES = [0.5, 5, 15, 30, 45, 60, 75, 90, 105, 120, 135, 150, 165, 180]

IN = 25.4
NO_HOST = ("FLAP", "TETHER", "PYRAMID", "ROOF")


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
        self.zoff = 0.0  # mm the surface sits off its own fold lines (display only)
        self.lift = 0.0  # mm the rig raises it off its parent near flat (display only)

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
        self.pull = {}  # flap uid -> pull 0..1 (the Pull slider)
        self.soft = set()  # panel pairs joined by a sliding bend, not a fold
        self.flaps = {}  # flap uid -> info for the UI and checks
        self.tubes = {}  # tube uid -> plan geometry for tethers
        self.tethers = {}
        self.frames = {}  # stage frame uid -> info
        self.stack_ok = set()  # mechanism label pairs whose tabs may overlap
        self.floors = []  # floor / ceiling uids built so far (frames clear them)
        self.edge_tab = {}  # floor ("bottom") / ceiling ("top") tab widths
        # mechanism uid -> (piece, pattern -> its line coordinates, bounds) for
        # drawn creases and cuts
        self.line_frames = {}
        self.doors = list(card.get("doors") or [])
        self.doors_done = set()
        # A carousel stage only ever opens to 360/n degrees; everything is
        # sampled and checked up to there.
        self.tmax = min(180.0, float(card.get("tmax", 180.0)))
        self.samples = sorted({s for s in SAMPLES if s < self.tmax - 1e-6} |
                              {self.tmax, round(0.5 * self.tmax, 3)})
        self.t_ref = min(90.0, 0.5 * self.tmax)  # a typical open angle for setting things up
        self.TABLE_T = [T_MIN] + [float(d) for d in range(1, int(math.ceil(self.tmax)))] + \
            [self.tmax]
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
                if not outs and self.panels[name].kind != "page":
                    self.warn(f"{lab}: uses up all of {self.panels[name].label}; make it "
                              f"smaller than its host so there's paper left round it")
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
        self.hosts[(0, "S")].key = 0

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
            h = m.get("host", 0) if m["type"] not in NO_HOST else 0
            ok = True
            if m["type"] == "TETHER":
                deps = [m.get("from_uid", 0)]
                if m.get("to") == "TUBE":
                    deps.append(m.get("to_uid", 0))
                for dep in deps:
                    d_ = by_uid.get(dep)
                    if d_ is None or d_["type"] != "TUBE":
                        self.warn(f"{m['label']}: pick the tube(s) it joins; skipped")
                        ok = False
                    elif not visit(d_):
                        ok = False
            if h:
                parent = by_uid.get(h)
                lid = parent is not None and parent["type"] == "TUBE" and \
                    parent.get("roof") == "FLAT" and parent.get("roof_fold") == "DIP"
                stage = parent is not None and parent["type"] == "STAGE"
                joint = parent is not None and parent["type"] in ("FLOOR", "CEILING")
                ffc = m["type"] in ("FRAME", "FLOOR", "CEILING")
                if joint and m.get("vside") == "V" and m["type"] != "VFOLD":
                    self.warn(f"{m['label']}: only V-folds stand on a floor's or ceiling's "
                              f"crease (it is a mountain fold from the stage side); use its "
                              f"corners for boxes and cubes; skipped")
                    ok = False
                elif parent is not None and (stage != ffc or (joint and ffc)):
                    self.warn(f"{m['label']}: frames, floors and ceilings go on a stage set, "
                              f"and only they do; skipped")
                    ok = False
                elif parent is not None and parent["type"] == "VFOLD" and (
                        m["type"] not in ("STANDUP", "BOX", "VFOLD", "MOUTH", "CUBE",
                                          "TUBE") or
                        (m.get("vside", "FL") != "V" and
                         (m["type"] not in ("STANDUP", "BOX", "CUBE", "TUBE", "VFOLD")
                          or m.get("style") == "CUT"))):
                    self.warn(f"{m['label']}: on a V-fold's crease go boxes, box layers, "
                              f"V-folds, mouths, cubes, tubes and stand-ups; in front of or "
                              f"behind a half stand-ups, glued boxes, cubes, tubes and "
                              f"V-folds; skipped")
                    ok = False
                elif parent is None or (parent["type"] not in ("BOX", "STANDUP", "VFOLD",
                                                               "CUBE")
                                        and not lid and not stage and not joint
                                        and not (parent["type"] == "TUBE" and
                                                 m.get("wall") in ("L", "R"))):
                    self.warn(f"{m['label']}: its host is missing (a box, or a tube with a "
                              f"dipped flat roof); skipped")
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

        # floors and ceilings first: frames are cut to clear them
        for m in sorted(self.mechs, key=lambda m: 0 if m["type"] in ("FLOOR", "CEILING") else 1):
            visit(m)
        for m in order:
            h = m.get("host", 0) if m["type"] not in NO_HOST else 0
            fold = m.get("fold", "A")
            if h and by_uid[h]["type"] == "TUBE":
                # a side wall's foot, or the roof's centre crease
                fold = {"L": "WL", "R": "WR"}.get(m.get("wall", "NONE"), "R")
            if h and by_uid[h]["type"] == "CUBE":
                fold = "WR" if m.get("wall") == "R" else "WL"  # a front wall's foot
            if h and by_uid[h]["type"] == "STAGE":
                fold = "S"  # the stage set's back crease
            if h and by_uid[h]["type"] in ("FLOOR", "CEILING"):
                fold = "L" if m.get("side", "L") == "L" else "R"  # its join with a wall
                if m.get("vside") == "V":
                    fold = "V"  # on its centre crease, from the stage side
            if h and by_uid[h]["type"] == "VFOLD":
                fold = m.get("vside", "FL")  # in front of / behind a half
            if h and fold == "V" and by_uid[h]["type"] == "BOX":
                # a strap's valley between two peaks, counted from the left
                host = self.hosts.get((h, f"V{int(m.get('gully', 1) or 1)}"))
            else:
                host = self.hosts.get((h, fold) if h else (0, "S"))
            if host is None:
                self.warn(f"{m['label']}: its host was skipped; skipped too")
                continue
            n0 = len(self.order)
            if m["type"] == "VFOLD":
                if m.get("cut_above"):
                    self._cut_above(m, host)
                self._vfold(m, host)
            elif m["type"] == "MOUTH":
                self._mouth(m, host)
            elif m["type"] == "BOX":
                self._box(m, host)
            elif m["type"] == "STANDUP":
                self._standup(m, host)
            elif m["type"] == "CUBE":
                self._cube(m, host)
            elif m["type"] == "FLAP":
                self._flap(m)
            elif m["type"] == "TUBE":
                self._tube(m, host)
            elif m["type"] == "TETHER":
                self._tether(m)
            elif m["type"] == "PYRAMID":
                self._pyramid(m, host)
            elif m["type"] == "STAGE":
                self._stage(m, host)
            elif m["type"] == "ROOF":
                self._roof_stage(m, host)
            elif m["type"] == "FRAME":
                self._frame(m, host)
            elif m["type"] in ("FLOOR", "CEILING"):
                self._floor(m, host)
            if isinstance(host.key, tuple):
                # standing in a floor's corner its tabs may lie over the
                # floor's own tab along the wall: glue on glue is fine
                self.stack_ok.add(frozenset((by_uid[h]["label"], m["label"])))
            if not host.trig:
                # the host's panels don't turn with the card's own angle, so
                # no closed form applies: every new fold is tabulated
                for name in self.order[n0:]:
                    hg = self.panels[name].hinge
                    if hg is not None and hg.kind in ("LINEAR", "SPHERICAL", "EXPR"):
                        hg.kind = "TABLE"
                    if hg is not None:
                        hg.host_bound = True  # rides a fold that may not open evenly
        self._card_lines()

    def _door_lines(self, piece, names, primary):
        """Door flaps cut in these panels, as extra lines in the pattern. A
        door on a face goes with the panels holding that face; a door on the
        whole piece with the piece's own creases (primary)."""
        from .openings import door_lines
        out = []
        for d in self.doors:
            if d["id"] in self.doors_done or (d.get("piece") or "Card") != piece:
                continue
            face = d.get("face") or ""
            if face:
                if face not in names or (face.startswith("Page.") and not primary):
                    continue
            elif not primary:
                continue
            out += door_lines(self, d)
            self.doors_done.add(d["id"])
        return out

    def _card_lines(self):
        """Extra creases and cuts in the card itself (the background): a
        ceiling or floor folded out of the pages, cut-out shapes. Pattern x
        across the card (left page negative), y up the spine."""
        self.line_frames[0] = ("Card", lambda q: q, None)
        lines = self.card.get("lines")
        from .folds import build as fold_build, expand
        doors = self._door_lines("Card", ["Page.L", "Page.R"], True)
        if lines or doors:
            fold_build(self, "Card", ["Page.L", "Page.R"], "Card", expand(lines) + doors,
                       "Card", float(self.card.get("pleat", 0.0) or 0.0))
        for d in self.doors:
            if d["id"] not in self.doors_done:
                self.warn(f"Door flap on {d.get('piece') or 'Card'}: door flaps work on the "
                          f"card, V-folds, box folds and box layers; cut as a hole")

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
        # Slant: the strip runs across the fold at an angle. Its creases stay
        # parallel to the fold (they must), so its outline is sheared along
        # it: a point x across the fold moves k x up it. Nothing else changes.
        k = math.tan(math.radians(max(-75.0, min(75.0, float(m.get("slant", 0.0))))))
        if host.is_spine and a + b > W + 1e-6:
            self.warn(f"{lab}: height + depth ({a + b:.0f} mm) is deeper than the "
                      f"page ({W:.0f} mm), so it sticks out when closed")
        if min(y0, y0 - k * a, y0 + k * b) < -1e-6 or \
                max(y0, y0 - k * a, y0 + k * b) + w > H + 1e-6:
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
            rect = [host.v1(-a, y0 - k * a), host.v1(b, y0 + k * b),
                    host.v1(b, y0 + w + k * b), host.v1(-a, y0 + w - k * a)]
            cells = self.carve(piece, rect, {host.p1, host.p2}, lab)
            if cells is None:
                return
            nx = host.d1(1.0, 0.0)
            pc = host.v1(b - a, y0)
            cb_cells, ac_cells = self.split_cells(cells, nx, nx[0] * pc[0] + nx[1] * pc[1])
            Tv = host.T1.inverted()  # pattern -> virtual

            def asm_ac(t):
                S, l, r, Y, nl, nr = host.dirs(t)
                return frame(S + a * l + a * r, r, Y) @ Tv

            def asm_cb(t):
                S, l, r, Y, nl, nr = host.dirs(t)
                return frame(S + b * r + b * l, -l, Y) @ Tv

            hA = host.T1 @ hinge_frame_2d((-a, y0), (0, 1))
            hC = host.T1 @ hinge_frame_2d((b - a, y0), (0, 1))
            ac = self.add(Panel(f"{base}.AC", piece, "panel", ac_cells, asm_ac, host.p1,
                                Hinge(hA, hA), f"{lab}: top"))
            cb = self.add(Panel(f"{base}.CB", piece, "panel", cb_cells, asm_cb,
                                ac.name if ac else host.p1,
                                Hinge(hC, hC) if ac else Hinge(hA, hA), f"{lab}: front"))
            if not (ac and cb):
                self.warn(f"{lab}: height or depth is too small to fold")
                return
            self.cut_panels |= {ac.name, cb.name}
            TA = host.T1 @ Matrix.Translation((-a, 0.0, 0.0))
            TC = host.T1 @ Matrix.Translation((b - a, 0.0, 0.0))
            TB = host.T1 @ Matrix.Translation((b, 0.0, 0.0))
        else:
            # Glued strip: tabA | AC (b) | CB (a) | tabB along u, width w along v
            t_ = min(float(m.get("tab", 12.0)), a, b)
            if float(m.get("tab", 12.0)) > min(a, b) + 1e-6:
                self.warn(f"{lab}: glue tabs shortened to {t_:.0f} mm to stay hidden")
            piece = f"Box{uid}"
            self.add_piece(Piece(piece, lab, 1 + uid, (0.0, w / 2)))
            ch = min(0.3 * t_, 0.25 * w)
            # Peaks: the strip zig-zags. The plain strap is one chevron, up
            # from gully A (direction r, b long) to the peak and down to gully
            # B (direction -l, a long). N peaks: N copies of it at 1/N scale
            # along the line between the gullies, so the valleys between
            # them stay on that line and the strip still lies flat when open.
            npk = max(1, min(8, int(m.get("peaks", 1) or 1)))
            L_ = a + b
            ub = [0.0]  # crease positions along the strip
            for i in range(npk):
                ub += [i * L_ / npk + b / npk, (i + 1) * L_ / npk]
            names = ["AC"] + [f"Z{j}" for j in range(1, 2 * npk - 1)] + ["CB"] if npk > 1 \
                else ["AC", "CB"]
            polys = [[(ub[j], 0), (ub[j + 1], 0), (ub[j + 1], w), (ub[j], w)]
                     for j in range(2 * npk)]
            poly_tabA = [(-t_, ch), (0, 0), (0, w), (-t_, w - ch)]
            poly_tabB = [(L_, 0), (L_ + t_, ch), (L_ + t_, w - ch), (L_, w)]
            if k:
                # each part moves k x up the fold, x where it lies on the
                # card when flat: the strip at x = u - a, the tabs folded
                # back under it at x = -a - u (A) and x = a + 2b - u (B)
                def sh(poly, x):
                    return [(u, v + k * x(u)) for u, v in poly]
                polys = [sh(pl, lambda u: u - a) for pl in polys]
                poly_tabA = sh(poly_tabA, lambda u: -a - u)
                poly_tabB = sh(poly_tabB, lambda u: a + 2 * b - u)

            def asm_tabA(t):
                S, l, r, Y, nl, nr = host.dirs(t)
                return frame(S + a * l + y0 * Y + lift1 * TAB_LIFT * nl, l, Y)

            def shape(t):
                """Fold line A, the line B - A between the gullies and the
                two sides' directions: the plain strap's chevron (exact,
                its folds turning with the card), which the peaks repeat."""
                S, l, r, Y, nl, nr = host.dirs(t)
                A_ = S + a * l + y0 * Y
                return A_, b * r - a * l, r, -l, Y

            def make_asm(j):
                i, up = divmod(j, 2)  # chevron i; up side (0) or down side (1)
                u0 = i * L_ / npk

                def asm(t):
                    A_, c, uA, uB, Y = shape(t)
                    V = A_ + (i / npk) * c  # its valley
                    if up == 0:
                        return frame(V - u0 * uA, uA, Y)
                    Q = V + (b / npk) * uA  # its peak
                    return frame(Q - (u0 + b / npk) * uB, uB, Y)
                return asm

            def asm_tabB(t):
                S, l, r, Y, nl, nr = host.dirs(t)
                return frame(S + (a + 2 * b) * r + y0 * Y + lift2 * TAB_LIFT * nr, -r, Y)

            self.add(Panel(f"{base}.TabA", piece, "tab", [poly_tabA], asm_tabA,
                           host.p1, None, f"{lab}: tab A"))
            prev = None
            for j in range(2 * npk):
                if npk == 1:
                    txt = ("top", "front")[j]
                else:
                    txt = f"peak {j // 2 + 1} {'up' if j % 2 == 0 else 'down'}"
                if prev is None:
                    hg = Hinge(host.T1 @ hinge_frame_2d((-a, y0), (0, 1)),
                               hinge_frame_2d((0, 0), (0, 1)))
                    par = host.p1
                else:
                    hg = Hinge(hinge_frame_2d((ub[j], 0), (0, 1)),
                               hinge_frame_2d((ub[j], 0), (0, 1)))
                    par = prev.name
                prev = self.add(Panel(f"{base}.{names[j]}", piece, "panel", [polys[j]],
                                      make_asm(j), par, hg, f"{lab}: {txt}"))
                if prev is not None and j == 0:
                    # shown resting on its glue tabs: open flat, the whole strip
                    # sits above them, not level with the page and under them.
                    # The rig lifts it off the page it hangs from as the card
                    # nears flat (lift), and not while it folds, so it never
                    # pokes through a page closing on it.
                    th = float(self.card.get("thickness", 0.0) or 0.0)
                    up_ = TAB_LIFT + 2.0 * th + 0.05 if th > 0 else 2.0 * TAB_LIFT
                    prev.lift = up_ * lift1
            self.add(Panel(f"{base}.TabB", piece, "tab", [poly_tabB], asm_tabB,
                           host.p2, None, f"{lab}: tab B"))
            TA = Matrix.Translation((0.0, -y0, 0.0))
            TC = Matrix.Translation((b, -y0, 0.0))
            TB = Matrix.Translation((a + b, -y0, 0.0))
            # the valleys between the peaks: folds opening like small spines
            for i in range(1, npk):
                uv = i * L_ / npk
                Tv = Matrix.Translation((uv, -y0, 0.0))
                hv = Host(self, f"{base}.{names[2 * i - 1]}", 0.0, 0.0,
                          f"{base}.{names[2 * i]}", 0.0, 0.0, f"{lab}: valley {i}",
                          Tv, Tv).finish()
                hv.trig = False
                self.hosts[(uid, f"V{i}")] = hv
        if m.get("style") == "CUT":
            Tv_ = host.T1.inverted()
            self.line_frames[uid] = (piece, lambda q: (
                (Tv_ @ Vector((q[0], q[1], 0.0)))[0] - (b - a),
                (Tv_ @ Vector((q[0], q[1], 0.0)))[1] - y0), (-b, a, 0.0, w))
        else:
            self.line_frames[uid] = (piece, lambda q: (q[0] - b, q[1]), (-b, a, 0.0, w))
        if f"{base}.AC" in self.panels and f"{base}.CB" in self.panels:
            # extra creases and cuts: X across from the front-top fold (C),
            # negative over the top, positive down the front; Y along the box
            from .folds import build as fold_build, expand
            if m.get("style") == "CUT":
                names = [host.p1, f"{base}.AC", f"{base}.CB", host.p2]
                to_pat = (lambda p: host.v1(b - a + p[0], y0 + p[1]))
            else:
                names = [f"{base}.AC", f"{base}.CB"]
                to_pat = (lambda p: (b + p[0], p[1]))
            doors = self._door_lines(piece, names, m.get("style") != "CUT")
            if m.get("lines") or doors:
                fold_build(self, piece, names, lab,
                           expand(m.get("lines"), to_pat, lambda p: (p[0], w - p[1])) + doors,
                           base, float(m.get("pleat", 0.0) or 0.0))
        if role:
            for n in (f"{base}.AC", f"{base}.CB"):
                if n in self.panels:
                    self.panels[n].label = self.panels[n].label.replace(": ", " (inset): ")
        AC, CB = f"{base}.AC", f"{base}.CB"
        single = int(m.get("peaks", 1) or 1) <= 1 or m.get("style") == "CUT"
        for key, p1, T1, p2, T2, txt in (
                ("A", host.p1, host.T1 @ Matrix.Translation((-a, 0.0, 0.0)), AC, TA, "on top"),
                ("C", AC, TC, CB, TC, "inset"),
                ("B", CB, TB, host.p2, host.T2 @ Matrix.Translation((b, 0.0, 0.0)), "in front")):
            if key == "C" and not single:
                continue  # several peaks: the top panel doesn't meet the front
            h = Host(self, p1, 0.0, 0.0, p2, 0.0, 0.0, f"{lab}: {txt}", T1, T2).finish()
            h.trig = host.trig
            self.hosts[(uid, key)] = h

    # ---------------------------------------------------- parallelogram stand-up
    def _standup(self, m, host):
        """Birmingham 38. A picture held parallel to the background by a small
        bridge (Upright), or parallel to the floor on a small leg (Flat, the
        flying carpet). Seen from the side it is a box fold: background a,
        bridge (or picture) b, picture (or leg) a, floor b; but the picture
        is its own piece, as wide and tall as you like, and the bridge or leg
        is a separate strip glued to its back."""
        uid = m["uid"]
        a, b = float(m["height"]), float(m["depth"])
        y0, w = float(m["y"]), float(m["width"])
        Wi, Hi = float(m.get("img_w", w)), float(m.get("img_h", a))
        t_ = float(m.get("tab", 10.0))
        lab = m["label"]
        flat = m.get("stand") == "FLAT"
        if Wi < w:
            self.warn(f"{lab}: picture narrower than its {'leg' if flat else 'bridge'}; "
                      f"widened to {w:.0f} mm")
            Wi = w
        need = b if flat else a
        if Hi < need:
            self.warn(f"{lab}: picture shorter than the {'leg reach' if flat else 'bridge height'}"
                      f"; lengthened to {need:.0f} mm")
            Hi = need
        if host.is_spine and a + b > self.W + 1e-6:
            self.warn(f"{lab}: height + depth ({a + b:.0f} mm) is deeper than the page, so it "
                      f"sticks out when closed")
        vc = 0.5 * w
        lift1, lift2 = host.lift
        base = f"Stand{uid}"
        AC, CB = f"{base}.AC", f"{base}.CB"
        img = self.add_piece(Piece(base, lab, 1 + uid, (0.0, 0.5 * Hi)))
        img.upright = True
        strip = f"Bridge{uid}"
        self.add_piece(Piece(strip, f"{lab} {'leg' if flat else 'bridge'}", 700 + uid,
                             (0.5 * (a + b), vc)))

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

        under = Matrix.Translation((0.0, 0.0, -TAB_LIFT))
        hw = 0.5 * Wi
        if not flat:
            # picture pattern: x along the fold, y up from the floor
            M = Matrix(((0, -1, 0, a + b), (1, 0, 0, vc), (0, 0, 1, 0), (0, 0, 0, 1)))
            tf = min(t_, b)
            ch = min(0.3 * tf, 0.25 * Wi)
            self.add(Panel(CB, base, "panel", [[(-hw, 0), (hw, 0), (hw, Hi), (-hw, Hi)]],
                           lambda t: asm_cb(t) @ M, host.p2,
                           Hinge(host.T2 @ hinge_frame_2d((b, y0 + vc), (0, 1)),
                                 hinge_frame_2d((0, 0), (1, 0))), f"{lab}: picture"))
            self.add(Panel(f"{base}.Foot", base, "tab",
                           [[(-hw + ch, -tf), (hw - ch, -tf), (hw, 0), (-hw, 0)]],
                           lambda t: asm_tabB(t) @ M, host.p2, None, f"{lab}: foot"))
            ta = min(t_, a - 1.0, b)
            tc = min(t_, a)
            cha, chc = min(0.3 * ta, 0.25 * w), min(0.3 * tc, 0.25 * w)
            self.add(Panel(f"{base}.TabA", strip, "tab",
                           [[(-ta, cha), (0, 0), (0, w), (-ta, w - cha)]], asm_tabA,
                           host.p1, None, f"{lab}: bridge tab on the background"))
            self.add(Panel(AC, strip, "panel", [[(0, 0), (b, 0), (b, w), (0, w)]], asm_ac,
                           host.p1, Hinge(host.T1 @ hinge_frame_2d((-a, y0), (0, 1)),
                                          hinge_frame_2d((0, 0), (0, 1))), f"{lab}: bridge"))
            self.add(Panel(f"{base}.TabC", strip, "tab",
                           [[(b, 0), (b + tc, chc), (b + tc, w - chc), (b, w)]],
                           lambda t: asm_cb(t) @ under, CB, None,
                           f"{lab}: bridge tab on the picture"))
            Mi = M.inverted()
            TA = Matrix.Translation((0.0, -y0, 0.0))
            TC1, TC2 = Matrix.Translation((b, -y0, 0.0)), Mi @ Matrix.Translation((b, -y0, 0.0))
            TB = Mi @ Matrix.Translation((a + b, -y0, 0.0))
        else:
            # picture pattern: x along the fold, y out from the background
            M = Matrix(((0, 1, 0, 0), (-1, 0, 0, vc), (0, 0, 1, 0), (0, 0, 0, 1)))
            tf = min(t_, a)
            ch = min(0.3 * tf, 0.25 * Wi)
            self.add(Panel(f"{base}.TabA", base, "tab",
                           [[(-hw, 0), (-hw + ch, -tf), (hw - ch, -tf), (hw, 0)][::-1]],
                           lambda t: asm_tabA(t) @ M, host.p1, None,
                           f"{lab}: tab on the background"))
            self.add(Panel(AC, base, "panel", [[(-hw, 0), (hw, 0), (hw, Hi), (-hw, Hi)]],
                           lambda t: asm_ac(t) @ M, host.p1,
                           Hinge(host.T1 @ hinge_frame_2d((-a, y0 + vc), (0, 1)),
                                 hinge_frame_2d((0, 0), (-1, 0))), f"{lab}: picture"))
            tc = min(t_, b)
            tb = min(t_, b)
            chc, chb = min(0.3 * tc, 0.25 * w), min(0.3 * tb, 0.25 * w)
            self.add(Panel(CB, strip, "panel", [[(b, 0), (a + b, 0), (a + b, w), (b, w)]],
                           asm_cb, host.p2,
                           Hinge(host.T2 @ hinge_frame_2d((b, y0), (0, 1)),
                                 hinge_frame_2d((a + b, 0), (0, 1))), f"{lab}: leg"))
            self.add(Panel(f"{base}.TabC", strip, "tab",
                           [[(b - tc, chc), (b, 0), (b, w), (b - tc, w - chc)]],
                           lambda t: asm_ac(t) @ under, AC, None, f"{lab}: leg tab under "
                           f"the picture"))
            self.add(Panel(f"{base}.Foot", strip, "tab",
                           [[(a + b, 0), (a + b + tb, chb), (a + b + tb, w - chb), (a + b, w)]],
                           asm_tabB, host.p2, None, f"{lab}: leg foot"))
            Mi = M.inverted()
            TA = Mi @ Matrix.Translation((0.0, -y0, 0.0))
            TC1 = Mi @ Matrix.Translation((b, -y0, 0.0))
            TC2 = Matrix.Translation((b, -y0, 0.0))
            TB = Matrix.Translation((a + b, -y0, 0.0))
        for key, p1, T1, p2, T2, txt in (
                ("A", host.p1, host.T1 @ Matrix.Translation((-a, 0.0, 0.0)), AC, TA, "on top"),
                ("C", AC, TC1, CB, TC2, "inset"),
                ("B", CB, TB, host.p2, host.T2 @ Matrix.Translation((b, 0.0, 0.0)), "in front")):
            h = Host(self, p1, 0.0, 0.0, p2, 0.0, 0.0, f"{lab}: {txt}", T1, T2).finish()
            h.trig = host.trig
            self.hosts[(uid, key)] = h

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
        if sgn is None and "pref" in J:
            # floors rise into the stage, ceilings drop into it
            tr = min(90.0, 0.5 * self.tmax)
            base, k, n, nl, nr, *_ = self._crease_parts(J, tr)
            want = J["host"].L(tr).to_3x3() @ Vector((J["pref"][0], J["pref"][1], 0.0))
            sgn = max((1.0, -1.0), key=lambda s: (base + s * k * n).normalized().dot(want))
            self._branch[key] = sgn
        if sgn is None:
            base, k, n, nl, nr, *_ = self._crease_parts(J, self.t_ref)
            want = nl + nr
            if J.get("gap") and self.normals_out(J["host"]):
                want = -want  # a host whose normals face out of its gap (a V-fold's crease)
            sgn = max((1.0, -1.0), key=lambda s: (base + s * k * n).normalized().dot(want))
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
        parent, Tp, g_page = ((host.p1, host.T1, J["uL"]) if L else (host.p2, host.T2, J["uR"]))
        Hp = Tp @ hinge_frame_2d((0.0, J["y"]), g_page)

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
        # an asymmetric V-fold can glue down along different lengths each side
        gs = {"L": g, "R": float(m.get("glue_r", g) or g)}
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
        # flip: the net drawn mirrored, so the printed side of each half
        # faces the other half (a stage set's background, seen from inside)
        fl = -1.0 if m.get("flip") else 1.0
        uLp = (-fl * math.sin(all_), math.cos(all_))
        uRp = (fl * math.sin(alr), math.cos(alr))
        self.joints[base] = dict(host=host, y=yP, uL=uLf, uR=uRf, aL=all_, aR=alr)
        if m.get("pref"):
            self.joints[base]["pref"] = m["pref"]

        # Pattern: crease along +Y' from P' = (0, 0); halves either side.
        GL = (gs["L"] * uLp[0], gs["L"] * uLp[1])
        GR = (gs["R"] * uRp[0], gs["R"] * uRp[1])
        Q = (0.0, Lc)
        shape = m.get("shape", "QUAD")
        # beak: a triangle to the crease's end; panel: a four-sided half.
        # Either side can be either (beak on one side, panel on the other)
        if shape in ("TRI", "BEAK_L"):
            halfL = [(0, 0), Q, GL]
        else:
            halfL = [(0, 0), Q, (GL[0], GL[1] + Lc), GL]
        if shape in ("TRI", "BEAK_R"):
            halfR = [(0, 0), GR, Q]
        else:
            halfR = [(0, 0), GR, (GR[0], GR[1] + Lc), Q]
        FcL = hinge_frame_2d((0, 0), uLp)
        FcR = hinge_frame_2d((0, 0), uRp)

        # Tabs: fold flat onto the host along the glue line, inside or outside
        bis = Vector((uLf[0] + uRf[0], uLf[1] + uRf[1], 0))
        if bis.length < 1e-6:
            bis = Vector((0, 1, 0))
        inside = m.get("tab_side", "IN") == "IN"
        tabs = []
        for side, uf, up, Fc, sigma in (("L", uLf, uLp, FcL, fl), ("R", uRf, uRp, FcR, -fl)):
            Xc = Vector((up[1], -up[0], 0))  # pattern X of the hinge frame
            s2 = -sigma * Xc  # tab side in the pattern (away from the half)
            q = Vector((uf[1], -uf[0], 0))
            if (q.dot(bis) > 0) != inside:
                q = -q
            lift = host.lift[0 if side == "L" else 1]
            # Tab pattern -> virtual page: Y'(up) -> uf, X' -> -sigma * q
            T = frame(Vector((0, yP, lift * TAB_LIFT)), -sigma * q,
                      Vector((uf[0], uf[1], 0))) @ Fc.inverted()
            gp = (gs[side] * up[0], gs[side] * up[1])
            ins = min(0.5 * t_, 0.3 * gs[side])
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

        self.line_frames[uid] = (piece, lambda q: q, None)
        halves = [f"{base}.HalfL", f"{base}.HalfR"]
        doors = self._door_lines(piece, halves, True)
        if m.get("lines") or doors:
            from .folds import build as fold_build, expand
            fold_build(self, piece, halves, lab, expand(m.get("lines")) + doors, base,
                       float(m.get("pleat", 0.0) or 0.0))

        self._vfold_hosts(uid, base, host, yP, (gs["L"], gs["R"]), Lc, (uLf, uRf), (uLp, uRp))

        tears = [s for s in self.samples if not self.crease(base, s)[3]]
        if tears:
            self.warn(f"{lab}: tears if opened past {min(tears):.0f} degrees (pointing "
                      f"forward, make each piece angle at least its glue angle; or turn on "
                      f"Fold Flat)")

    def _vfold_hosts(self, uid, base, host, yP, gs, Lc, uf, up):
        """Each half's glue line is a fold too: a stand-up (or a glued box)
        can stand in front of a half (FL, FR: between it and the page outside
        the V) or behind it (BL, BR: inside the V). The half is the
        background, the page the floor; positions run out along the glue
        line from the V point. These folds don't open with the card's own
        angle, so what stands on them is tabulated."""
        # its own centre crease: a spine of its own, the halves its pages (in
        # the piece's pattern the crease runs up x = 0, both halves alike)
        hl, hr = f"{base}.HalfL", f"{base}.HalfR"
        if hl in self.panels and hr in self.panels:
            def cx(n):
                pts = [q for poly in self.panels[n].polys for q in poly]
                return sum(q[0] for q in pts) / max(1, len(pts))
            p1, p2 = (hl, hr) if cx(hl) < cx(hr) else (hr, hl)
            h = Host(self, p1, 0.0, 0.0, p2, 0.0, 0.0,
                     f"{self.panels[hl].label.split(':')[0]}: crease").finish()
            h.trig = False
            h.size = (max(gs), Lc)
            h.key = (uid, "V")
            self.hosts[(uid, "V")] = h
        bis = Vector((uf[0][0] + uf[1][0], uf[0][1] + uf[1][1], 0.0))
        if bis.length < 1e-6:
            bis = Vector((0.0, 1.0, 0.0))
        for side, k in (("L", 0), ("R", 1)):
            half = f"{base}.Half{side}"
            if half not in self.panels:
                continue
            u_f = Vector((uf[k][0], uf[k][1], 0.0))
            u_p = Vector((up[k][0], up[k][1], 0.0))
            # into the half, away from its glue edge (towards the centre fold)
            into = Vector((u_p.y, -u_p.x, 0.0))
            if into.dot(Vector((0.0, Lc, 0.0))) < 0:
                into = -into
            inside = Vector((u_f.y, -u_f.x, 0.0))  # on the page, into the V
            if inside.dot(bis) < 0:
                inside = -inside
            page, Tp = (host.p1, host.T1) if side == "L" else (host.p2, host.T2)
            T1 = frame(Vector((0.0, 0.0, 0.0)), -into, u_p)
            for key, x2, txt in (("F" + side, -inside, "in front of"),
                                 ("B" + side, inside, "behind")):
                T2 = Tp @ frame(Vector((0.0, yP, 0.0)), x2, u_f)
                h = Host(self, half, 0.0, 0.0, page, 0.0, 0.0,
                         f"{self.panels[half].label} ({txt})", T1, T2).finish()
                h.trig = False
                h.size = (gs[k], Lc)
                h.key = (uid, key)  # its foot may sit on the V-fold's own tab
                self.hosts[(uid, key)] = h

    def _wall_host(self, uid, key, wall, w_org, w_foot, w_up, page, Tp, p_org, p_foot,
                   p_out, label, size):
        """The fold where a wall standing on a page meets it, seen from
        outside: the wall is the background (virtual left page), the page
        the floor beyond it (virtual right). Positions run along the wall's
        foot from w_org (p_org on the page). Like a V-fold's glue folds,
        what stands here is tabulated."""
        if wall not in self.panels or page not in self.panels:
            return None
        T1 = frame(Vector((w_org[0], w_org[1], 0.0)), -Vector((w_up[0], w_up[1], 0.0)),
                   Vector((w_foot[0], w_foot[1], 0.0)))
        T2 = Tp @ frame(Vector((p_org[0], p_org[1], 0.0)), Vector((p_out[0], p_out[1], 0.0)),
                        Vector((p_foot[0], p_foot[1], 0.0)))
        h = Host(self, wall, 0.0, 0.0, page, 0.0, 0.0, label, T1, T2).finish()
        h.trig = False
        h.size = size
        h.key = (uid, key)
        self.hosts[(uid, key)] = h
        return h

    # ------------------------------------------------------------------ cube
    def _cube(self, m, host):
        """180-degree cube standing on one vertical edge on the fold.

        Four walls in a strip: back-left A, front-left B, front-right C,
        back-right D, closed by a tab on A glued inside D. B and C are a
        V-fold on the fold (glue lines at 45 degrees, square corners), glued
        down by base tabs; A and D complete the parallelogram. The optional
        lid is two right triangles on B and C, creased along the diagonal and
        joined by a glue tab: it folds as a V on the front corner, peaked or
        dipped."""
        uid, lab = m["uid"], m["label"]
        sz, hgt = float(m["size"]), float(m["height"])
        # a rectangular base: the front-left wall (and the back-right) wB
        # wide, the front-right (and back-left) wC; a square when equal
        wB = sz
        wC = float(m.get("size_r", 0.0) or 0.0) or sz
        y0 = float(m["y"])
        tb = min(float(m.get("tab", 10.0)), 0.45 * min(wB, wC))
        piece = f"Cube{uid}"
        self.add_piece(Piece(piece, lab, 1 + uid, (wB + wC, 0.5 * hgt)))
        key = f"{piece}.V"
        r2 = math.sqrt(0.5)
        uLf, uRf = (-r2, r2), (r2, r2)
        self.joints[key] = dict(host=host, y=y0, uL=uLf, uR=uRf,
                                aL=math.pi / 2, aR=math.pi / 2, gap=True)
        if host.is_spine and (y0 < 0 or y0 + (wB + wC) * r2 > self.H):
            self.warn(f"{lab}: runs past the top or bottom of the card")
        # strip pattern: tab | A [0,wC] | B (wB) | C (wC) | D (wB)
        s1, s2, s3, s4 = wC, wC + wB, 2 * wC + wB, 2 * (wC + wB)
        square = abs(wB - wC) < 1e-6
        self.pieces[piece].wrap = [0.0, 0.0, s4, hgt]  # the four walls, round
        B = [(s1, 0), (s2, 0), (s2, hgt), (s1, hgt)]
        C = [(s2, 0), (s3, 0), (s3, hgt), (s2, hgt)]
        A = [(0, 0), (s1, 0), (s1, hgt), (0, hgt)]
        D = [(s3, 0), (s4, 0), (s4, hgt), (s3, hgt)]
        ch = min(0.3 * tb, 0.2 * hgt)
        close = [(-tb, ch), (0, 0), (0, hgt), (-tb, hgt - ch)]
        hb = self._half(f"{piece}.B", piece, [B], (s2, 0), (-1, 0), (0, 1), "L", key,
                        f"{lab}: front left")
        hc = self._half(f"{piece}.C", piece, [C], (s2, 0), (1, 0), (0, 1), "R", key,
                        f"{lab}: front right")

        def parts(t):
            c, uL, uR, ok, P3 = self.crease(key, t)
            return c, uL, uR, P3

        def pat(o):
            return frame(v3(o), (1, 0, 0), (0, 1, 0)).inverted()

        def asm_a(t):
            c, uL, uR, P3 = parts(t)
            return frame(P3 + wB * uL, -uR, c) @ pat((s1, 0))

        def asm_d(t):
            c, uL, uR, P3 = parts(t)
            return frame(P3 + wC * uR, uL, c) @ pat((s3, 0))

        def asm_close(t):
            c, uL, uR, P3 = parts(t)
            nD = uL.cross(c).normalized()
            return frame(P3 + wB * uL + wC * uR - TAB_LIFT * nD, uL, c) @ pat((0, 0))

        # side corners: the angle between the front walls' bottom edges,
        # cos = uL . uR = cos^2(t/2)
        def corner(t):
            return math.acos(max(-1.0, min(1.0, math.cos(math.radians(max(t, T_MIN)) / 2) ** 2)))

        cex = "acos(cos(radians(T)/2)*cos(radians(T)/2))"
        hy = hinge_frame_2d((s1, 0), (0, 1))
        self.add(Panel(f"{piece}.A", piece, "panel", [A], asm_a, hb.name,
                       Hinge(hy, hy, "EXPR", dict(var="t", fn=corner, expr=cex)),
                       f"{lab}: back left"))
        hy2 = hinge_frame_2d((s3, 0), (0, 1))
        dd = self.add(Panel(f"{piece}.D", piece, "panel", [D], asm_d, hc.name,
                            Hinge(hy2, hy2, "EXPR", dict(var="t", fn=corner, expr=cex)),
                            f"{lab}: back right"))
        self.add(Panel(f"{piece}.Close", piece, "tab", [close], asm_close, dd.name, None,
                       f"{lab}: closing tab"))

        # base tabs: B and C glue to the host along their bottom edges
        inside = m.get("tab_side", "IN") == "IN"
        for side, poly_u, gdir, q, parent, Tp, sgn in (
            ("L", (s1, s2), uLf, (r2, r2), host.p1, host.T1, -1.0),
            ("R", (s2, s3), uRf, (-r2, r2), host.p2, host.T2, 1.0),
        ):
            qv = Vector((q[0], q[1], 0)) * (1 if inside else -1)
            gv = Vector((gdir[0], gdir[1], 0))
            lift = host.lift[0 if side == "L" else 1]
            # strip (u, v<0) -> virtual page: along the edge, and off it by -v
            o_strip = s2
            xdir = -gv if side == "L" else gv  # strip +u direction on the page
            T = frame(Vector((0, y0, lift * TAB_LIFT)), xdir, -qv) @ pat((o_strip, 0))
            u0, u1 = poly_u
            poly = [(u0 + ch, -tb), (u0, 0), (u1, 0), (u1 - ch, -tb)]
            # keep each tab on its own side of the fold
            n2 = (sgn * T[0][0], sgn * T[0][1])
            poly = clip_halfplane(poly, n2, 0.5 - sgn * T[0][3])
            pa = self.panels[parent].asm
            Tpat = Tp @ T
            self.add(Panel(f"{piece}.Tab{side}", piece, "tab", [poly],
                           (lambda t, pa=pa, T=Tpat: pa(t) @ T), parent, None,
                           f"{lab}: base tab {side}"))

        # the folds where the front walls meet the page, outside the cube
        for wkey, wall, foot, page, Tp, uf in (
                ("WL", f"{piece}.B", (-1.0, 0.0), host.p1, host.T1, uLf),
                ("WR", f"{piece}.C", (1.0, 0.0), host.p2, host.T2, uRf)):
            out = Vector((uf[1], -uf[0], 0.0))
            if out.y > 0:  # away from the cube (the bisector of its glue lines is +y)
                out = -out
            self._wall_host(uid, wkey, wall, (s2, 0.0), foot, (0.0, 1.0), page, Tp,
                            (0.0, y0), uf, out[:2],
                            f"{lab}: {'front left' if wkey == 'WL' else 'front right'} wall",
                            (wB if wkey == "WL" else wC, hgt))

        lid = m.get("lid", "PEAK")
        if lid != "NONE" and not square:
            self.warn(f"{lab}: a lid creased corner to corner only folds flat on a square "
                      f"base; this one is left open (set the widths equal for a lid)")
            lid = "NONE"
        if lid != "NONE":
            sg = 1.0 if lid == "PEAK" else -1.0

            Lh = math.hypot(wB, wC)

            def lid_dir(t):
                # the lid's far corner Q, from the front-top corner: wB from
                # the left lid's corner, wC from the right's, Lh from it;
                # peaked (up) or dipped (down) out of the walls' top plane
                c, uL, uR, P3 = parts(t)
                G = max(-0.999999, min(0.999999, uL.dot(uR)))
                x = (wB - G * wC) / (1 - G * G)
                y = (wC - G * wB) / (1 - G * G)
                z2 = Lh * Lh - (x * x + y * y + 2 * x * y * G)
                Q = x * uL + y * uR + sg * math.sqrt(max(z2, 0.0)) * c
                return Q.normalized(), c, uL, uR, P3, Q

            def asm_lb(t):
                cp, c, uL, uR, P3, Q = lid_dir(t)
                return frame(P3 + hgt * c, -uL, Q - wB * uL) @ pat((s2, hgt))

            def asm_lc(t):
                cp, c, uL, uR, P3, Q = lid_dir(t)
                return frame(P3 + hgt * c, uR, Q - wC * uR) @ pat((s2, hgt))

            LB = [(s2, hgt), (s1, hgt), (s1, hgt + wC)]
            LC = [(s2, hgt), (s3, hgt), (s3, hgt + wB)]
            # glue tab on the right lid's diagonal, tucked under the left lid
            d = Vector((wC, wB, 0)).normalized()
            nrm = Vector((-wB, wC, 0)).normalized()
            P0 = Vector((s2, hgt, 0))
            # the triangle it glues to narrows to its corners
            gt = min(tb, 0.18 * math.sqrt(2) * min(wB, wC))
            tab_poly = [tuple((P0 + d * 0.15 * Lh)[:2]), tuple((P0 + d * 0.85 * Lh)[:2]),
                        tuple((P0 + d * 0.8 * Lh + nrm * gt)[:2]),
                        tuple((P0 + d * 0.2 * Lh + nrm * gt)[:2])]
            fn = (lambda t: math.atan2(math.sin(math.radians(t) / 2),
                                       sg * math.sqrt(2) * math.cos(math.radians(t) / 2)))
            ex = (f"atan2(sin(radians(T)/2),{sg * math.sqrt(2):.9g}*cos(radians(T)/2))")
            ht = hinge_frame_2d((s2, hgt), (-1, 0))
            ht2 = hinge_frame_2d((s2, hgt), (1, 0))
            if square:  # closed form
                hl_ = Hinge(ht, ht, "EXPR", dict(var="t", fn=lambda t: fn(max(t, T_MIN)), expr=ex))
                hr_ = Hinge(ht2, ht2, "EXPR", dict(var="t", fn=lambda t: fn(max(t, T_MIN)), expr=ex))
            else:  # a rectangle: sampled
                hl_ = Hinge(ht, ht, "TABLE", {})
                hr_ = Hinge(ht2, ht2, "TABLE", {})
            lb = self.add(Panel(f"{piece}.LidL", piece, "panel", [LB], asm_lb, hb.name, hl_,
                                f"{lab}: lid left"))
            self.add(Panel(f"{piece}.LidR", piece, "panel", [LC], asm_lc, hc.name, hr_,
                           f"{lab}: lid right"))

            def asm_lt(t):
                cp, c, uL, uR, P3, Q = lid_dir(t)
                M = asm_lb(t)
                nL = M.to_3x3() @ Z
                into = (uL - uL.dot(cp) * cp).normalized()  # across the crease, into the left lid
                return frame(P3 + hgt * c - TAB_LIFT * nL, cp, into) \
                    @ frame(v3((s2, hgt)), (wC, wB, 0), (-wB, wC, 0)).inverted()

            self.add(Panel(f"{piece}.LidTab", piece, "tab", [tab_poly], asm_lt, lb.name, None,
                           f"{lab}: lid glue tab"))

        tears = [t for t in self.samples if not self.crease(key, t)[3]]
        if tears:
            self.warn(f"{lab}: cannot fold below {max(tears):.0f} degrees")

    # ----------------------------------------------------- parallel strips
    def normals_out(self, host):
        """Does this host give normals facing out of the gap between its
        pages (a V-fold's crease does), not into it like the card's spine?"""
        flips = self.__dict__.setdefault("_strip_flip", {})
        k = id(host)
        if k not in flips:
            _, l0, r0, _, nl0, nr0 = host.dirs(min(90.0, 0.5 * self.tmax))
            flips[k] = (r0 - l0).dot(nl0 - nr0) < 0.0
        return flips[k]

    def strip_frame(self, host, t):
        """Plan frame shared by everything standing on parallel sticking
        strips. Every wall leans along e (half-way between the pages) and
        every crease is parallel to e, so seen along e the structure is a
        flat linkage. A strip at distance a from the fold sits at plan
        x = -/+ a sin(t/2), with its foot a cos(t/2) up e."""
        t = max(t, T_MIN)
        S, l, r, Y, nl, nr = host.dirs(t)
        # some hosts (a V-fold's crease) give normals facing out of the gap
        # between their pages, not into it: turn them round, once per host
        if self.normals_out(host):
            nl, nr = -nl, -nr
        # l + r and nl + nr both point along e, r - l and nl - nr along xh;
        # adding them keeps e and xh accurate both near shut and near flat
        e = (nl + nr + l + r).normalized()
        xh = (r - l + nl - nr).normalized()
        sn = r.dot(xh)
        cs = l.dot(e)
        return S, e, xh, Y, sn, cs

    def plan3d(self, host, a, t, pt):
        S, e, xh, Y, sn, cs = self.strip_frame(host, t)
        return S + a * cs * e + pt[0] * xh + pt[1] * Y

    def tube_plan(self, uid, t):
        T = self.tubes[uid]
        host, a, y0, D = T["host"], T["a"], T["y0"], T["D"]
        S, e, xh, Y, sn, cs = self.strip_frame(host, t)
        x = a * sn
        pf = math.sqrt(max(T["wf"] ** 2 - x * x, 0.0))
        pb = math.sqrt(max(T["wb"] ** 2 - x * x, 0.0))
        return dict(BL=(-x, y0 + D), FL=(-x, y0), FR=(x, y0), BR=(x, y0 + D),
                    CF=(0.0, y0 - T["sf"] * pf), CB=(0.0, y0 + D + T["sb"] * pb))

    def _wall_asm(self, host, a, P, Q, u0, pts_fn):
        """Wall standing along e from plan point P to Q (keys into pts_fn(t)),
        its pattern starting at u = u0."""
        Pi = frame(Vector((u0, 0, 0)), (1, 0, 0), (0, 1, 0)).inverted()

        def asm(t):
            pts = pts_fn(t)
            S, e, xh, Y, sn, cs = self.strip_frame(host, t)
            p3 = self.plan3d(host, a, t, pts[P])
            q3 = self.plan3d(host, a, t, pts[Q])
            return frame(p3, (q3 - p3).normalized(), e) @ Pi

        return asm

    def _tube(self, m, host):
        """Tube on two parallel sticking strips (Birmingham 51, 67, 68). The
        side walls are glued to strips at distance a either side of the fold;
        the front and back are pairs of walls creased vertically above the
        fold, pointing Out (hexagon), In (recessed) or flat when the pair is
        as wide as the strips are apart (box)."""
        uid, lab = m["uid"], m["label"]
        a, y0 = float(m["x"]), float(m["y"])
        D, hgt = float(m["depth"]), float(m["height"])
        wf, wb = max(float(m["front"]), a), max(float(m["back"]), a)
        if float(m["front"]) < a - 1e-6 or float(m["back"]) < a - 1e-6:
            self.warn(f"{lab}: front and back walls must be at least as wide as the strip "
                      f"distance; widened to {a:.0f} mm")
        sf = 1.0 if m.get("front_style", "OUT") == "OUT" else -1.0
        sb = 1.0 if m.get("back_style", "OUT") == "OUT" else -1.0
        tb = min(float(m.get("tab", 10.0)), 0.45 * D)
        if sf < 0 and sb < 0 and wf + wb > D + 1e-6:
            self.warn(f"{lab}: recessed front and back meet inside the tube when closed "
                      f"(make it longer or the walls narrower)")
        if host.is_spine and a + hgt > self.W + 1e-6:
            self.warn(f"{lab}: strip distance + height is more than the page width, so it "
                      f"sticks out when closed")
        if host.is_spine and (y0 - sf * wf < -1e-6 or y0 + D + sb * wb > self.H + 1e-6):
            self.warn(f"{lab}: runs past the top or bottom of the card")
        self.tubes[uid] = dict(host=host, a=a, y0=y0, D=D, wf=wf, wb=wb, sf=sf, sb=sb, h=hgt,
                               label=lab)
        piece = f"Tube{uid}"
        self.add_piece(Piece(piece, lab, 1 + uid, (D + wf, 0.5 * hgt)))
        pts = lambda t: self.tube_plan(uid, t)
        # strip pattern: F_L | G_fl | G_fr | F_R | G_br | G_bl | closing tab
        u = [0.0, D, D + wf, D + 2 * wf, 2 * D + 2 * wf, 2 * D + 2 * wf + wb,
             2 * D + 2 * wf + 2 * wb]
        self.pieces[piece].wrap = [0.0, 0.0, u[6], hgt]  # all six walls, round
        names = ["FL_", "GFL", "GFR", "FR_", "GBR", "GBL"]
        ends = [("BL", "FL"), ("FL", "CF"), ("CF", "FR"), ("FR", "BR"), ("BR", "CB"), ("CB", "BL")]
        labels = ["left side", "front left", "front right", "right side", "back right",
                  "back left"]
        walls = {}
        for i, nm in enumerate(names):
            poly = [(u[i], 0), (u[i + 1], 0), (u[i + 1], hgt), (u[i], hgt)]
            walls[nm] = dict(poly=poly, asm=self._wall_asm(host, a, ends[i][0], ends[i][1], u[i], pts),
                             u0=u[i])
        tab_hinge = lambda u_: hinge_frame_2d((u_, 0), (0, 1))
        P = {}
        # side walls hinge on the strips
        P["FL_"] = self.add(Panel(f"{piece}.FL_", piece, "panel", [walls["FL_"]["poly"]],
                                  walls["FL_"]["asm"], host.p1,
                                  Hinge(host.T1 @ hinge_frame_2d((-a, y0 + D), (0, -1)),
                                        hinge_frame_2d((0, 0), (1, 0))),
                                  f"{lab}: left side"))
        P["FR_"] = self.add(Panel(f"{piece}.FR_", piece, "panel", [walls["FR_"]["poly"]],
                                  walls["FR_"]["asm"], host.p2,
                                  Hinge(host.T2 @ hinge_frame_2d((a, y0), (0, 1)),
                                        hinge_frame_2d((u[3], 0), (1, 0))),
                                  f"{lab}: right side"))
        for nm, parent, hu, lb in (("GFL", "FL_", u[1], "front left"),
                                   ("GFR", "GFL", u[2], "front right"),
                                   ("GBR", "FR_", u[4], "back right"),
                                   ("GBL", "GBR", u[5], "back left")):
            P[nm] = self.add(Panel(f"{piece}.{nm}", piece, "panel", [walls[nm]["poly"]],
                                   walls[nm]["asm"], P[parent].name,
                                   Hinge(tab_hinge(hu), tab_hinge(hu), "TABLE", {}),
                                   f"{lab}: {lb}"))
        # closing tab on the back-left wall, glued inside the left side
        ch = min(0.3 * tb, 0.2 * hgt)
        close = [(u[6], 0), (u[6] + tb, ch), (u[6] + tb, hgt - ch), (u[6], hgt)]
        Pc = frame(Vector((u[6], 0, 0)), (1, 0, 0), (0, 1, 0)).inverted()

        def asm_close(t):
            p = pts(t)
            S, e, xh, Y, sn, cs = self.strip_frame(host, t)
            b3 = self.plan3d(host, a, t, p["BL"])
            f3 = self.plan3d(host, a, t, p["FL"])
            return frame(b3 + TAB_LIFT * xh, (f3 - b3).normalized(), e) @ Pc

        self.add(Panel(f"{piece}.Close", piece, "tab", [close], asm_close, P["FL_"].name, None,
                       f"{lab}: closing tab"))
        # base tabs under the side walls, folded in (towards the fold) or out
        k = 1.0 if m.get("tab_side", "IN") == "IN" else -1.0
        for side, u0, u1, T, parent, Tp in (
            ("L", u[0], u[1], frame(Vector((-a, y0 + D, TAB_LIFT)), (0, -1, 0), (-k, 0, 0)),
             host.p1, host.T1),
            ("R", u[3], u[4], frame(Vector((a, y0, TAB_LIFT)), (0, 1, 0), (k, 0, 0)),
             host.p2, host.T2),
        ):
            T = T @ frame(Vector((u0, 0, 0)), (1, 0, 0), (0, 1, 0)).inverted()
            c2 = min(0.3 * tb, 0.2 * D)
            poly = [(u0 + c2, -tb), (u0, 0), (u1, 0), (u1 - c2, -tb)]
            sgn = -1.0 if side == "L" else 1.0
            n2 = (sgn * T[0][0], sgn * T[0][1])
            poly = clip_halfplane(poly, n2, 0.5 - sgn * T[0][3])
            pa = self.panels[parent].asm
            Tpat = Tp @ T
            self.add(Panel(f"{piece}.Tab{side}", piece, "tab", [poly],
                           (lambda t, pa=pa, T=Tpat: pa(t) @ T), parent, None,
                           f"{lab}: base tab {side}"))
        # the folds where the side walls meet the page, outside the tube
        self._wall_host(uid, "WL", P["FL_"].name, (0.0, 0.0), (1.0, 0.0), (0.0, 1.0),
                        host.p1, host.T1, (-a, y0 + D), (0.0, -1.0), (-1.0, 0.0),
                        f"{lab}: left side wall", (D, hgt))
        self._wall_host(uid, "WR", P["FR_"].name, (u[3], 0.0), (1.0, 0.0), (0.0, 1.0),
                        host.p2, host.T2, (a, y0), (0.0, 1.0), (1.0, 0.0),
                        f"{lab}: right side wall", (D, hgt))
        # which wall a tether glues to at each point, and the way along it
        self.tubes[uid]["attach"] = dict(
            FL=(P["FL_"].name, "BL"), BL=(P["FL_"].name, "FL"),
            FR=(P["FR_"].name, "BR"), BR=(P["FR_"].name, "FR"),
            CF=(P["GFL"].name, "FL"), CB=(P["GBR"].name, "BR"))
        roof = m.get("roof", "NONE")
        roof = {True: "POINTED", False: "NONE"}.get(roof, roof)
        if roof == "POINTED":
            self._roof(uid, f"Roof{uid}", f"{lab} roof", 300 + uid, host, a, y0, D, wf, wb,
                       sf, sb, hgt, float(m.get("roof_height", 30.0)),
                       float(m.get("ridge", 0.0)), tb, "IN",
                       walls=(P["FL_"].name, P["FR_"].name))
        elif roof == "FLAT":
            self._flat_roof(uid, f"{lab} roof", host, a, y0, D, wf, wb, sf, sb, hgt,
                            float(m.get("eave", 0.0)), m.get("roof_fold", "PEAK"), tb,
                            P["FL_"], P["FR_"], u[3], float(m.get("rib", 0.0)))

    def _flat_roof(self, uid, lab, host, a, y0, D, wf, wb, sf, sb, hgt, eave, fold, tb,
                   wl, wr, u3, rib=0.0):
        """Flat roof on a tube: two halves creased down the middle above the
        fold, each hinged on a side wall's top edge by a tab folded in off the
        wall and glued underneath. Eave lets it overhang the walls all round.

        A half of width a hinged at plan x = -a sin(t/2) reaches the mirror
        plane a cos(t/2) above (Peak) or below (Dip) its hinge: flat when the
        card is open, standing up (or tucked down inside the walls) when shut."""
        k = 1.0 if fold == "PEAK" else -1.0
        piece = f"Roof{uid}"
        self.add_piece(Piece(piece, lab, 300 + uid, (0.0, y0 + 0.5 * D)))
        pfo = sf * math.sqrt(max(wf * wf - a * a, 0.0))
        pbo = sb * math.sqrt(max(wb * wb - a * a, 0.0))
        out = a + hgt + (a if k > 0 else 0.0) + (eave if k < 0 else 0.0)
        if out > self.W + 1e-6:
            self.warn(f"{lab}: lies {out:.0f} mm out from the fold when shut, more than the "
                      f"page width, so it sticks out")
        if k > 0 and eave > hgt + 1e-6:
            self.warn(f"{lab}: an eave deeper than the walls are tall hits the page as "
                      f"the card shuts")
        if k < 0 and a > hgt + 1e-6:
            self.warn(f"{lab}: a dipped roof tucks {a:.0f} mm down inside walls only "
                      f"{hgt:.0f} mm tall; use Peak or taller walls")
        if k < 0 and (sf < 0 or sb < 0):
            self.warn(f"{lab}: a dipped roof runs into ends that point in; use Peak")
        if y0 - max(pfo, 0.0) - eave < -1e-6 or y0 + D + max(pbo, 0.0) + eave > self.H + 1e-6:
            self.warn(f"{lab}: runs past the top or bottom of the card")

        # left half outline at open, grown by the eave on its outer edges
        outline = [(0.0, y0 + D + pbo), (-a, y0 + D), (-a, y0), (0.0, y0 - pfo)]

        def line(p, q, d):
            """Edge p -> q moved d to its left (the outline runs anticlockwise)."""
            ux, uy = q[0] - p[0], q[1] - p[1]
            L = math.hypot(ux, uy)
            nx, ny = -uy / L, ux / L
            return (p[0] + d * nx, p[1] + d * ny), (ux / L, uy / L)

        def meet(l1, l2):
            (p, u), (q, v) = l1, l2
            den = u[0] * v[1] - u[1] * v[0]
            if abs(den) < 1e-9:
                return q
            s_ = ((q[0] - p[0]) * v[1] - (q[1] - p[1]) * v[0]) / den
            return (p[0] + s_ * u[0], p[1] + s_ * u[1])

        e_ = max(eave, 0.0)
        lines = [line(outline[i], outline[i + 1], -e_) for i in range(3)]
        mid = ((0.0, 0.0), (0.0, 1.0))
        polyL = [meet(mid, lines[0]), meet(lines[0], lines[1]), meet(lines[1], lines[2]),
                 meet(lines[2], mid)]
        if ccw(polyL) and poly_area(ccw(polyL)) < 1.0:
            self.warn(f"{lab}: roof too small; skipped")
            return
        polyR = [(-x, y) for x, y in polyL]

        def dirs(t):
            S, e, xh, Y, sn, cs = self.strip_frame(host, t)
            fL = S + (a * cs + hgt) * e - a * sn * xh
            dL = sn * xh + k * cs * e
            C0 = fL + a * dL
            return C0, dL, (sn * xh - k * cs * e), Y

        def asm_L(t):  # pattern x = -a on the hinge, 0 on the crease
            C0, dL, dR, Y = dirs(t)
            return frame(C0, dL, Y)

        def asm_R(t):
            C0, dL, dR, Y = dirs(t)
            return frame(C0, dR, Y)

        HL = self.add(Panel(f"{piece}.L", piece, "panel", [polyL], asm_L, wl.name, None,
                            f"{lab}: left half"))
        HL.hinge = self._hinge_on(wl.name, asm_L, (-a, y0 + D), (-a, y0))
        HR = self.add(Panel(f"{piece}.R", piece, "panel", [polyR], asm_R, wr.name, None,
                            f"{lab}: right half"))
        HR.hinge = self._hinge_on(wr.name, asm_R, (a, y0), (a, y0 + D))
        # tabs folded in off the wall tops, glued under the halves
        w = min(tb, a - 1.0)
        if w < 3.0:
            self.warn(f"{lab}: strips too close to the fold for roof tabs")
            return
        c = min(0.3 * w, 0.2 * D)
        for side, wall, half, u0, F in (
                ("L", wl, HL, 0.0, frame(Vector((-a, y0 + D, -TAB_LIFT)), (0, -1, 0), (1, 0, 0))),
                ("R", wr, HR, u3, frame(Vector((a, y0, -TAB_LIFT)), (0, 1, 0), (-1, 0, 0)))):
            poly = [(u0, hgt), (u0 + D, hgt), (u0 + D - c, hgt + w), (u0 + c, hgt + w)]
            sg = -1.0 if side == "L" else 1.0
            if side == "L":
                fwd = lambda q: (-a + q[1] - hgt, y0 + D - q[0])
                back = lambda q: (y0 + D - q[1], hgt + q[0] + a)
            else:
                fwd = lambda q, u0=u0: (a - (q[1] - hgt), y0 + q[0] - u0)
                back = lambda q, u0=u0: (u0 + q[1] - y0, hgt + a - q[0])
            # keep it under the half (ends that point in cut across it)
            on = [fwd(q) for q in poly]
            for n2, d2 in halfplanes(ccw(half.polys[0])):
                if abs(n2[0] * sg * a + n2[1] * y0 - d2) < 1e-6 and \
                        abs(n2[0] * sg * a + n2[1] * (y0 + D) - d2) < 1e-6:
                    continue
                on = clip_halfplane(on, n2, d2 + 0.3)
                if len(on) < 3:
                    break
            if len(on) < 3:
                continue
            poly = [back(q) for q in on]
            A = F @ frame(Vector((u0, hgt, 0)), (1, 0, 0), (0, 1, 0)).inverted()
            asm_h = half.asm
            self.add(Panel(f"Tube{uid}.Top{side}", f"Tube{uid}", "tab", [poly],
                           (lambda t, f=asm_h, A=A: f(t) @ A), half.name, None,
                           f"{lab}: roof tab {side}"))
        if k < 0:
            # A dipped roof's crease stays the wall height above the spine,
            # straight up the mirror plane, and its halves stay parallel to
            # the pages: a second spine for other mechanisms (Birmingham 67/68).
            self.hosts[(uid, "R")] = Host(self, HL.name, 0.0, 0.0, HR.name, 0.0, 0.0,
                                          lab).finish()
            if rib > 0:
                self._rib(uid, lab, host, y0, D, hgt, a, tb, w, rib, HL, HR)

    def _glue_asm(self, target, src_asm, e0, e1, side_src, side_tgt, below=False,
                  t=None):
        """Placement for a tab hanging off edge e0-e1 of a panel (placed by
        src_asm) that folds over and glues flat on target, on the side_tgt
        side of that edge (target pattern), on its back if below."""
        t = min(90.0, 0.5 * self.tmax) if t is None else t
        Rel = target.asm(t).inverted() @ src_asm(t)
        q0, q1 = Rel @ v3(e0), Rel @ v3(e1)
        q0.z = q1.z = 0.0
        for q in (q0, q1):  # a doubled layer sits a hair off the fold: put it on it
            if abs(q.x) < 0.5:
                q.x = 0.0
        Fp = frame(v3(e0), v3((e1[0] - e0[0], e1[1] - e0[1])), v3(side_src))
        Fq = frame(q0, q1 - q0, v3(side_tgt))
        A = Matrix.Translation((0, 0, -TAB_LIFT if below else TAB_LIFT)) @ Fq @ Fp.inverted()
        return lambda t, f=target.asm, A=A: f(t) @ A

    def _rib(self, uid, lab, host, y0, D, hgt, a, tb, wroof, rib, HL, HR):
        """Centre rib: a doubled strip standing straight up the mirror plane
        from the spine to the roof crease, holding the roof up. Each layer is
        glued to one page at the bottom and under the other roof half at the
        top."""
        L = min(rib, D)
        y1 = y0 + 0.5 * (D - L)
        y2 = y1 + L
        w = min(tb, a - tb - 2.0, a - wroof - 2.0)
        if w < 3.0:
            self.warn(f"{lab}: no room between the strips for the centre rib's tabs")
            return
        piece = f"Rib{uid}"
        self.add_piece(Piece(piece, f"{lab} rib", 600 + uid, (y1 + L, 0.5 * hgt)))

        def asm1(t):
            S, e, xh, Y, sn, cs = self.strip_frame(host, t)
            return frame(S, Y, e)

        W1 = self.add(Panel(f"{piece}.W1", piece, "panel", [[(y1, 0), (y2, 0), (y2, hgt),
                                                             (y1, hgt)]], asm1, host.p1, None,
                            f"{lab}: rib"))
        W1.hinge = self._hinge_on(host.p1, asm1, (y1, 0.0), (y2, 0.0))
        W1.hinge.kind = "LINEAR"
        # second layer folded back round the end, glued behind the first
        G = frame(Vector((2 * y2, 0.0, -2 * TAB_LIFT)), (-1, 0, 0), (0, 1, 0))
        asm2 = (lambda t, G=G: asm1(t) @ G)
        W2 = self.add(Panel(f"{piece}.W2", piece, "panel", [[(y2, 0), (y2 + L, 0),
                                                             (y2 + L, hgt), (y2, hgt)]],
                            asm2, W1.name, None, f"{lab}: rib back"))
        c = min(0.3 * w, 0.2 * L)
        pages = {"L": self.panels[host.p1], "R": self.panels[host.p2]}
        for nm, u0, asm, v, out, tgt, side, below in (
                ("AL", y1, asm1, 0.0, -1.0, pages["L"], (-1.0, 0.0), False),
                ("CR", y1, asm1, hgt, 1.0, HR, (1.0, 0.0), True),
                ("AR", y2, asm2, 0.0, -1.0, pages["R"], (1.0, 0.0), False),
                ("CL", y2, asm2, hgt, 1.0, HL, (-1.0, 0.0), True)):
            poly = [(u0, v), (u0 + L, v), (u0 + L - c, v + out * w), (u0 + c, v + out * w)]
            tasm = self._glue_asm(tgt, asm, (u0, v), (u0 + L, v), (0.0, out), side, below)
            self.add(Panel(f"{piece}.{nm}", piece, "tab", [poly], tasm, tgt.name, None,
                           f"{lab}: rib tab"))

    def _pyramid(self, m, host):
        """Pyramid or tent standing straight on two parallel sticking strips
        (Birmingham 52): sloping sides glued to the strips meet at an apex,
        or at a ridge above the fold; the ends are creased down the middle
        above the fold and float free at the bottom."""
        uid, lab = m["uid"], m["label"]
        if not host.is_spine:
            self.warn(f"{lab}: pyramids stand on the card spine for now")
        a, y0 = float(m["x"]), float(m["y"])
        D = float(m["depth"])
        wf, wb = max(float(m["front"]), a), max(float(m["back"]), a)
        if float(m["front"]) < a - 1e-6 or float(m["back"]) < a - 1e-6:
            self.warn(f"{lab}: front and back must be at least as wide as the strip "
                      f"distance; widened to {a:.0f} mm")
        sf = 1.0 if m.get("front_style", "OUT") == "OUT" else -1.0
        sb = 1.0 if m.get("back_style", "OUT") == "OUT" else -1.0
        tb = min(float(m.get("tab", 10.0)), 0.45 * D)
        self._roof(uid, f"Pyramid{uid}", lab, 1 + uid, host, a, y0, D, wf, wb, sf, sb, 0.0,
                   float(m["height"]), float(m.get("ridge", 0.0)), tb,
                   m.get("tab_side", "IN"))

    # ----------------------------------------------------------- stage set
    def _frame(self, m, host):
        """Stage frame (Birmingham 118): a panel across the stage, glued by a
        tab down each side to the pages at Depth from the spine, with a
        centre crease that folds back towards the spine as the stage closes.
        Each half is Depth x sin(open/2) wide, so the frame pulls flat
        exactly when the stage is fully open (360/n degrees in a carousel):
        it is the frames, floors and ceilings that stop the stage there."""
        uid, lab = m["uid"], m["label"]
        if not host.is_spine and host.open_max is None:
            self.warn(f"{lab}: frames stand in a stage (a carousel stage or a stage set)")
            return
        om = host.open_max or self.tmax
        Wd, Hd = host.size or (self.W, self.H)
        a = min(float(m["x"]), Wd)
        y0 = max(0.0, float(m.get("y", 0.0)))
        y1 = min(Hd, y0 + float(m.get("height", Hd)))
        B = a * math.sin(math.radians(0.5 * om))
        if a < 5.0 or y1 - y0 < 5.0 or B < 3.0:
            self.warn(f"{lab}: too small; skipped")
            return
        piece = f"Frame{uid}"
        self.add_piece(Piece(piece, lab, 1 + uid, (0.0, 0.5 * (y0 + y1)))).upright = True

        def dirs(t):
            S, e, xh, Y, sn, cs = self.strip_frame(host, t)
            s = math.sqrt(max(B * B - a * a * sn * sn, 0.0))
            fL = S + a * cs * e - a * sn * xh
            dL = (a * sn * xh - s * e) / B  # crease dips towards the spine
            dR = (a * sn * xh + s * e) / B
            return fL + B * dL, dL, dR, Y

        def asm_L(t):
            C0, dL, dR, Y = dirs(t)
            return frame(C0, dL, Y)

        def asm_R(t):
            C0, dL, dR, Y = dirs(t)
            return frame(C0, dR, Y)

        # Floors rise into the stage and ceilings drop into it as it closes:
        # cut the frame's bottom (top) back so it clears them all the way.
        polyL = [(-B, y0), (0, y0), (0, y1), (-B, y1)]
        for fl, fkey in self.floors:
            if fkey != host.key:
                continue
            half = self.panels.get(f"VFold{fl}.HalfL")
            if half is None:
                continue
            for t in self.samples:
                if t > self.tmax - 0.5:
                    continue
                F, M = half.asm(t), asm_L(t)
                nF = F.to_3x3() @ Z
                n2 = (nF.dot(M.col[0].to_3d()), nF.dot(M.col[1].to_3d()))
                if math.hypot(*n2) < 0.2:
                    continue  # lying flat together: stacked, not crossing
                d0 = nF.dot(M.translation - F.translation)
                mid = (-0.5 * B, 0.5 * (y0 + y1))
                if n2[0] * mid[0] + n2[1] * mid[1] + d0 < 0:
                    n2, d0 = (-n2[0], -n2[1]), -d0
                polyL = clip_halfplane(polyL, n2, 1.0 - d0)
                if len(polyL) < 3:
                    self.warn(f"{lab}: squeezed out by the floor or ceiling; skipped")
                    return
        polyR = [(-x, y) for x, y in polyL]
        HL = self.add(Panel(f"{piece}.L", piece, "panel", [polyL], asm_L, host.p1, None,
                            f"{lab}: left half"))
        HL.hinge = self._hinge_on(host.p1, asm_L, (-B, y1), (-B, y0))
        HR = self.add(Panel(f"{piece}.R", piece, "panel", [polyR], asm_R, host.p2, None,
                            f"{lab}: right half"))
        HR.hinge = self._hinge_on(host.p2, asm_R, (B, y0), (B, y1))
        # closed form: the half's angle to its page
        h_ = "radians(T)/2"
        q_ = f"sqrt(max({B * B:.9g}-{a * a:.9g}*sin({h_})*sin({h_}),0))"
        ex = f"atan2(-{q_},{a:.9g}*sin({h_}))-{h_}"

        def fn(t):
            hh = math.radians(max(t, T_MIN)) / 2
            q = math.sqrt(max(B * B - a * a * math.sin(hh) ** 2, 0.0))
            return math.atan2(-q, a * math.sin(hh)) - hh

        if host.is_spine:  # opening = the card's: closed form; on a stage set, tabulated
            for hh in (HL, HR):
                hh.hinge.kind = "EXPR"
                hh.hinge.sph = dict(var="t", fn=fn, expr=ex)
        # side tabs fold back behind the frame and glue to the pages, clear of
        # the floor's and ceiling's tabs along the page edges
        w = min(float(m.get("tab", 8.0)), 0.5 * a)
        ys = [q[1] for q in polyL if abs(q[0] + B) < 1e-6] or [y0, y1]
        ya, yb = min(ys), max(ys)
        et = self.edge_tab.get(host.key, {})
        if "bottom" in et:
            ya = max(ya, et["bottom"] + 1.0)
        if "top" in et:
            yb = min(yb, Hd - et["top"] - 1.0)
        c = min(0.3 * w, 0.2 * (yb - ya))
        for side, half, x, sgn, pg in (("L", HL, -B, -1.0, host.p1), ("R", HR, B, 1.0, host.p2)):
            if yb - ya < 4.0:
                break
            poly = [(x, ya), (x, yb), (x + sgn * w, yb - c), (x + sgn * w, ya + c)]
            tasm = self._glue_asm(self.panels[pg], half.asm, (x, ya), (x, yb),
                                  (sgn, 0.0), (-sgn, 0.0))
            self.add(Panel(f"{piece}.Tab{side}", piece, "tab", [poly], tasm, pg, None,
                           f"{lab}: side tab {side}"))
        self.frames[uid] = dict(depth=a, width=2 * B, label=lab, host=host.key, open=om)

    def _floor(self, m, host):
        """Floor (or ceiling) of a stage: a V-fold whose glue lines run along
        the bottom (top) edges of the pages, straight out from the fold. Its
        two halves meet the pages at half the stage angle, so it lies flat
        when the stage is fully open and folds up into the stage (down, for a
        ceiling) as it closes."""
        ceiling = m["type"] == "CEILING"
        om = host.open_max or self.tmax
        Wd, Hd = host.size or (self.W, self.H)
        if host.open_max is not None and not ceiling:
            self.warn(f"{m['label']}: a stage set stands on the card, which is its floor; "
                      f"skipped")
            return
        if not host.is_spine and host.open_max is None:
            self.warn(f"{m['label']}: floors and ceilings go in a stage; skipped")
            return
        if om > 150.0:
            # flat at 180 it would have to lie in the page planes a moment
            # later: paper can't do that, so floors need three stages or more
            self.warn(f"{m['label']}: floors and ceilings need a stage angle under 150 "
                      f"degrees (three or more stages); skipped")
            return
        depth = min(float(m.get("depth", Wd)), Wd)
        al = 0.5 * om
        ca, sa = math.cos(math.radians(al)), math.sin(math.radians(al))
        # Its centre crease can run on past the front of the stage (a pointed
        # apron): shut, the crease lies on the page at half the stage angle
        # to the edge it's glued along, so it may reach Wd / cos and Hd / sin.
        lead = max(0.0, float(m.get("lead", 0.0)))
        Lc = depth * ca + lead
        Lmax = min(Wd / ca, Hd / sa) - 0.5
        if Lc > Lmax + 1e-6:
            self.warn(f"{m['label']}: its point can reach {Lmax - depth * ca:.0f} mm past the "
                      f"front at most before it sticks out when shut; shortened")
            Lc = Lmax
        d = dict(m, type="VFOLD", phi_l=90.0, phi_r=90.0, alpha_l=al, alpha_r=al,
                 glue=depth, height=Lc, shape="TRI",
                 y=Hd if ceiling else 0.0, tab_side="OUT" if ceiling else "IN",
                 pref=(0.0, -1.0) if ceiling else (0.0, 1.0),
                 flip=not ceiling)  # printed side into the stage
        self._vfold(d, host)
        base = f"VFold{m['uid']}"
        # its own crease (the V-fold host made by _vfold) from the stage side
        # is the far side of a mountain fold: V-folds stand there (they fold
        # flat over the crease as the stage shuts), boxes can't
        if f"{base}.HalfL" in self.panels:
            self.floors.append((m["uid"], host.key))
            self.edge_tab.setdefault(host.key, {})["top" if ceiling else "bottom"] = \
                float(m.get("tab", 8.0))
            self._joint_hosts(m, host, base)

    def _joint_hosts(self, m, host, base):
        """Where a floor or ceiling meets each wall is a fold too: hosts for
        box folds, V-folds and the rest standing in that corner (Side picks
        the left or right wall). Position runs out from the stage's fold."""
        for side, page, half in (("L", host.p1, f"{base}.HalfL"),
                                 ("R", host.p2, f"{base}.HalfR")):
            hp = self.panels[half].hinge
            Hp, Fc = hp.Hp, hp.Fc  # the glue line in the wall's and the half's patterns
            # which side of the glue line each lies on (its own X)
            def side_of(panel, F):
                Fi = F.inverted()
                xs = [(Fi @ Vector((q[0], q[1], 0))).x for poly in self.panels[panel].polys
                      for q in poly]
                return 1.0 if sum(xs) > 0 else -1.0
            sw, sh = side_of(page, Hp), side_of(half, Fc)
            if sw == sh:
                continue  # printed faces don't face into the corner
            T1, p1, T2, p2 = (Hp, page, Fc, half) if sw < 0 else (Fc, half, Hp, page)
            h = Host(self, p1, 0.0, 0.0, p2, 0.0, 0.0, f"{m['label']}: {side} wall",
                     T1, T2).finish()
            if h.lift != (1.0, 1.0):
                continue
            h.trig = False
            h.key = (m["uid"], side)
            self.hosts[(m["uid"], side)] = h

    def _cut_above(self, m, host):
        """A V-fold roof or ceiling on the spine: cut the background away
        above its glue lines (each side at its own glue angle)."""
        lab = m["label"]
        if not host.is_spine:
            self.warn(f"{lab}: Cut Away Background Above works on the card's spine; "
                      f"not cut")
            return
        W, H = self.W, self.H
        yP = float(m.get("y", 0.0))
        if not 0.0 < yP < H - 1e-6:
            return
        for sx, key in ((-1.0, "phi_l"), (1.0, "phi_r")):
            phi = float(m.get(key, m.get("phi_l", 60.0)))
            if phi <= 90.5:
                self.warn(f"{lab}: its glue lines rise from the spine, so the cut would "
                          f"take the V-fold's own ground; not cut (set the Glue Angle "
                          f"over 90)")
                return
        for sx, key in ((-1.0, "phi_l"), (1.0, "phi_r")):
            phi = float(m.get(key, m.get("phi_l")))
            sp, cp = math.sin(math.radians(phi)), math.cos(math.radians(phi))
            yE = yP + W * cp / sp
            region = [(0.0, yP), (0.0, H), (sx * W, H), (sx * W, yE)]
            if yE < 0.0:
                xb = -yP * sp / cp
                region = [(0.0, yP), (0.0, H), (sx * W, H), (sx * W, 0.0), (sx * xb, 0.0)]
            self.carve("Card", region, {"Page.L", "Page.R"},
                       f"{lab} cut-away {'left' if sx < 0 else 'right'}")

    def _roof_stage(self, m, host):
        """A peaked roof over a stage (or a card): the background is cut to a
        gable along two eaves lines falling from the spine, and a V-fold is
        glued along them with its crease rising to a ridge. Shut, the roof
        lies flat in the cut-away corners; open, it stands over the stage,
        its ridge level at full opening (a stage) or at 90 degrees (a card)
        with Level Ridge, or at the piece angle given.

        Valley: the same upside down (the card folds the same either way
        up): the background cut away below two lines rising from the spine,
        a V-fold floor glued along them dipping to a valley."""
        lab = m["label"]
        valley = bool(m.get("valley"))
        what = "valley floor" if valley else "roof"
        if not host.is_spine:
            self.warn(f"{lab}: a {what} goes on the card's spine; skipped")
            return
        W, H = self.W, self.H
        y = max(0.0, min(float(m.get("y", 0.85 * H)), H))
        yR = H - y if valley else y  # worked in roof terms: the card upside down
        phi = float(m.get("phi_l", 100.0))
        if phi <= 92.0:
            self.warn(f"{lab}: the slope must run away from the spine past level (over 90 "
                      f"degrees); set to 100")
            phi = 100.0
        phiA = 180.0 - phi if valley else phi  # the V-fold's real glue angle
        sp, cp = math.sin(math.radians(phi)), math.cos(math.radians(phi))
        reach = min(W / sp, yR / max(-cp, 1e-6))  # to the side edge, or the far edge
        g = min(float(m.get("glue", reach)), reach)

        def flip(pts):
            return [(x, H - yy) for x, yy in pts] if valley else pts

        # cut the background away beyond the eaves lines
        yE = yR + W * cp / sp
        for sx in (-1.0, 1.0):
            region = [(0.0, yR), (0.0, H), (sx * W, H), (sx * W, yE)]
            if yE < 0.0:  # the eaves reach the far edge first
                xb = -yR * sp / cp
                region = [(0.0, yR), (0.0, H), (sx * W, H), (sx * W, 0.0), (sx * xb, 0.0)]
            if yR < H - 1e-6:
                self.carve("Card", flip(region), {"Page.L", "Page.R"},
                           f"{lab} {'cut-away' if valley else 'gable'}")
        # level at the stage's full opening; a whole card is level at 90
        # degrees (flat open, a roof can only lie flat)
        tm = self.tmax if self.tmax < 179.0 else 90.0
        sA, cA = math.sin(math.radians(phiA)), math.cos(math.radians(phiA))
        up = -1.0 if valley else 1.0

        def crease_up(al):
            key = f"__roof{m['uid']}"
            self.joints[key] = dict(host=host, y=y, uL=(-sA, cA), uR=(sA, cA),
                                    aL=math.radians(al), aR=math.radians(al),
                                    pref=(0.0, up))
            self._branch.pop(key, None)
            c = self.crease(key, tm)[0]
            Y = host.L(tm).to_3x3() @ Vector((0.0, 1.0, 0.0))
            del self.joints[key]
            self._branch.pop(key, None)
            return up * c.dot(Y)

        al = float(m.get("alpha_l", 70.0))
        if m.get("level", True):
            lo, hi = 5.0, 89.0  # the ridge climbs as the piece angle grows
            if crease_up(lo) > 0 or crease_up(hi) < 0:
                self.warn(f"{lab}: no piece angle levels the ridge at this slope; "
                          f"using {al:.0f}")
            else:
                for _ in range(40):
                    mid = 0.5 * (lo + hi)
                    if crease_up(mid) > 0:
                        hi = mid
                    else:
                        lo = mid
                al = 0.5 * (lo + hi)
        # shut, the crease lies at (slope - piece angle) from the spine: past
        # this length it pokes out of the closed card
        tilt = math.radians(phi - al)
        ct, st_ = abs(math.cos(tilt)), abs(math.sin(tilt))
        fit = min((H - yR) / ct if ct > 1e-6 else 1e9, W / st_ if st_ > 1e-6 else 1e9) - 0.5
        Lc = max(1.0, float(m.get("height", 60.0)))
        if Lc > fit + 1e-6:
            self.warn(f"{lab}: its {'valley' if valley else 'ridge'} sticks out of the closed "
                      f"card by {Lc - fit:.0f} mm (fits up to {fit:.0f} mm; start it further "
                      f"from the {'bottom' if valley else 'top'} edge, or change the slope "
                      f"or the piece angle)")
        d = dict(m, type="VFOLD", phi_l=phiA, phi_r=phiA, alpha_l=al, alpha_r=al, glue=g,
                 height=Lc, shape="TRI", y=y, tab_side=m.get("tab_side", "IN"),
                 pref=(0.0, up), flip=valley, lines=m.get("lines", []))
        n0 = len(self.warnings)
        self._vfold(d, host)
        for i in range(n0, len(self.warnings)):
            w = self.warnings[i]
            if w.startswith(f"{lab}: tears if opened past"):
                deg = w.split("past ")[1].split(" ")[0]
                self.warnings[i] = (f"{lab}: a {'peaked roof' if not valley else 'valley floor'} can't open out flat; it tears "
                                    f"past {deg} degrees (it's made for carousel stages, "
                                    f"which open less)")
        self.roofs = getattr(self, "roofs", {})
        self.roofs[m["uid"]] = dict(alpha=al, ridge=Lc, eaves=g, reach=reach, fit=fit)

    def _stage(self, m, host):
        """Stage set in a card (Birmingham 118 on a V-fold): the background is
        a V-fold whose halves are square to its centre crease, glued along its
        bottom edges at the Glue Angle either side of the fold. It opens to
        twice the glue angle when the card is flat; frames and a ceiling stand
        in it as in a carousel stage, sized to pull flat right then."""
        phi = float(m.get("phi_l", 60.0))
        if not 10.0 <= phi <= 85.0:
            self.warn(f"{m['label']}: glue angle must be between 10 and 85 degrees")
            phi = max(10.0, min(85.0, phi))
        A, Hs = float(m["glue"]), float(m["height"])
        low = Hs * math.sin(math.radians(phi))
        if float(m["y"]) < low - 1e-6:
            self.warn(f"{m['label']}: shut, its back crease lies {low:.0f} mm down the card "
                      f"from where it stands; move it at least that far up")
        d = dict(m, type="VFOLD", phi_l=phi, phi_r=phi, alpha_l=90.0, alpha_r=90.0,
                 shape="QUAD", tab_side=m.get("tab_side", "OUT"), flip=True)
        self._vfold(d, host)
        base = f"VFold{m['uid']}"
        if f"{base}.HalfL" not in self.panels:
            return
        self.pieces[base].upright = True
        # seen from inside the stage the card's right half is on the left
        h = Host(self, f"{base}.HalfR", 0.0, 0.0, f"{base}.HalfL", 0.0, 0.0, m["label"]).finish()
        h.open_max, h.size, h.key = 2.0 * phi, (A, Hs), m["uid"]
        h.trig = False
        self.hosts[(m["uid"], "S")] = h

    def _hinge_on(self, parent, asm, c0, c1, t=None):
        """Hinge for a panel (pattern fold line c0 -> c1, placed by asm) on a
        parent panel: the same line found in the parent's pattern."""
        t = min(90.0, 0.5 * self.tmax) if t is None else t
        Rel = self.panels[parent].asm(t).inverted() @ asm(t)
        p0, p1 = Rel @ v3(c0), Rel @ v3(c1)
        return Hinge(hinge_frame_2d(p0[:2], (p1 - p0)[:2]),
                     hinge_frame_2d(c0, (c1[0] - c0[0], c1[1] - c0[1])), "TABLE", {})

    def _roof(self, uid, piece, lab, slot, host, a, y0, D, wf, wb, sf, sb, b, rise, ridge,
              tb, tab_side, walls=None):
        """Two sloping sides hinged on lines parallel to the fold at distance a
        (the sticking strips, or the top edges of a tube's side walls at
        height b), meeting above the fold at an apex (ridge 0) or a ridge;
        each end is a pair of triangles creased down the middle.

        A side of slope length h hinged at plan x = -a sin(t/2) reaches the
        mirror plane at height sqrt(h^2 - a^2 sin^2(t/2)) above its hinge, so
        the sides lie flat outwards when shut, like the tube walls. An end
        triangle hangs from its side's sloping edge; its crease foot is kept
        on the mirror plane (so the two halves meet) and floats free."""
        if rise <= 0.5:
            self.warn(f"{lab}: roof height must be more than zero")
            return
        h = math.hypot(a, rise)
        ridge = max(0.0, min(ridge, D))
        yr1 = y0 + 0.5 * (D - ridge)
        yr2 = yr1 + ridge
        if a + b + h > self.W + 1e-6:
            self.warn(f"{lab}: lies {a + b + h:.0f} mm out from the fold when shut, more than "
                      f"the page width, so it sticks out")
        pfo = sf * math.sqrt(max(wf * wf - a * a, 0.0))  # end points out at open
        pbo = sb * math.sqrt(max(wb * wb - a * a, 0.0))
        if y0 - max(pfo, 0.0) < -1e-6 or y0 + D + max(pbo, 0.0) > self.H + 1e-6:
            self.warn(f"{lab}: runs past the top or bottom of the card")
        self.add_piece(Piece(piece, lab, slot, (0.0, y0 + 0.5 * D)))

        def P3(t, px, py, v):
            S, e, xh, Y, sn, cs = self.strip_frame(host, t)
            return S + v * e + px * xh + py * Y

        def sides(t):
            """Hinge foot and slope directions of the left and right sides."""
            S, e, xh, Y, sn, cs = self.strip_frame(host, t)
            s = math.sqrt(max(h * h - a * a * sn * sn, 0.0))
            fL = S + (a * cs + b) * e - a * sn * xh
            fR = S + (a * cs + b) * e + a * sn * xh
            return fL, (a * sn * xh + s * e) / h, fR, (a * sn * xh - s * e) / h, Y

        def asm_L(t):  # pattern x = -h on the hinge, 0 at the ridge
            fL, dL, fR, dR, Y = sides(t)
            return frame(fL + h * dL, dL, Y)

        def asm_R(t):  # pattern x = 0 at the ridge, h on the hinge
            fL, dL, fR, dR, Y = sides(t)
            return frame(fL + h * dL, dR, Y)

        polyL = [(-h, y0), (0.0, yr1), (0.0, yr2), (-h, y0 + D)]
        polyR = [(0.0, yr1), (h, y0), (h, y0 + D), (0.0, yr2)]
        if walls is None:
            parL, parR = host.p1, host.p2
        else:
            parL, parR = walls
        PL = self.add(Panel(f"{piece}.SL", piece, "panel", [polyL], asm_L, parL,
                            None, f"{lab}: left slope"))
        PL.hinge = self._hinge_on(parL, asm_L, (-h, y0 + D), (-h, y0))
        PR = self.add(Panel(f"{piece}.SR", piece, "panel", [polyR], asm_R, parR,
                            None, f"{lab}: right slope"))
        PR.hinge = self._hinge_on(parR, asm_R, (h, y0), (h, y0 + D))

        # ----- ends: (ridge end Q, side corner C, crease foot M) on each side
        def solve_foot(A, B, d1, d2, xh, S, sg):
            """Point at d1 from A and d2 from B on the mirror plane."""
            L = (B - A).length
            u = (B - A) / L
            al = (d1 * d1 - d2 * d2 + L * L) / (2 * L)
            rho = math.sqrt(max(d1 * d1 - al * al, 0.0))
            F = A + al * u
            w1 = xh - u * xh.dot(u)
            k = w1.length
            w1 = w1 / k
            w2 = u.cross(w1)
            c = max(-1.0, min(1.0, -xh.dot(F - S) / (rho * k)))
            return F + rho * (c * w1 + sg * math.sqrt(1 - c * c) * w2)

        ends = []
        for end, yc, yq, po in (("F", y0, yr1, pfo), ("B", y0 + D, yr2, -pbo)):
            ym = yc - po  # crease foot at open (front points to smaller y)
            # 3D lengths at open (flat card): C=(-a,yc,b), Q=(0,yq,b+rise), M=(0,ym,b)
            d1 = math.hypot(a, yc - ym)          # C - M
            d2 = math.hypot(yq - ym, rise)       # Q - M
            dq = math.sqrt(a * a + (yq - yc) ** 2 + rise * rise)  # Q - C

            def geo(t, yc=yc, yq=yq):
                S, e, xh, Y, sn, cs = self.strip_frame(host, t)
                C = P3(t, -a * sn, yc, a * cs + b)
                Cr = P3(t, a * sn, yc, a * cs + b)
                Q = P3(t, 0.0, yq, a * cs + b + math.sqrt(max(h * h - a * a * sn * sn, 0.0)))
                return S, xh, C, Cr, Q

            # which of the two feet: the one at the open position. A flat end
            # (no point) can crease either way as the card starts to close:
            # Pointed Out sends the crease foot outwards, In tucks it under.
            S, xh, C, Cr, Q = geo(180.0)
            want = P3(180.0, 0.0, ym, b)
            ft = {g: solve_foot(C, Q, d1, d2, xh, S, g) for g in (1.0, -1.0)}
            if (ft[1.0] - ft[-1.0]).length > 0.05:
                sg = min(ft, key=lambda g: (ft[g] - want).length)
            else:
                S, xh, C, Cr, Q = geo(170.0)
                Y = self.strip_frame(host, 170.0)[3]
                out = -1.0 if end == "F" else 1.0  # outwards along the fold
                style = sf if end == "F" else sb
                sg = max((1.0, -1.0), key=lambda g: style * out *
                         (solve_foot(C, Q, d1, d2, xh, S, g) - C).dot(Y))

            # pattern: triangle across the left side's edge C-Q, then the right
            # half across the crease Q-M
            Cp, Qp = Vector((-h, yc)), Vector((0.0, yq))
            inner = Vector((-h, y0 + D if end == "F" else y0))  # a point on the side

            def place(P0, P1, r0, r1, away):
                """Point at r0 from P0 and r1 from P1, on the far side of P0-P1 from away."""
                L_ = (P1 - P0).length
                u_ = (P1 - P0) / L_
                n_ = Vector((-u_.y, u_.x))
                al_ = (r0 * r0 - r1 * r1 + L_ * L_) / (2 * L_)
                ht = math.sqrt(max(r0 * r0 - al_ * al_, 0.0))
                if n_.dot(away - P0) > 0:
                    n_ = -n_
                return P0 + al_ * u_ + ht * n_

            Mp = place(Cp, Qp, d1, d2, inner)
            Crp = place(Qp, Mp, dq, d1, Cp)
            Mp, Crp = (Vector((float(Mp.x), float(Mp.y))), Vector((float(Crp.x), float(Crp.y))))

            def asm_half(t, sg=sg, d1=d1, d2=d2, geo=geo, Cp=Cp, Qp=Qp, Mp=Mp, Crp=Crp,
                         right=False):
                S, xh, C, Cr, Q = geo(t)
                M = solve_foot(C, Q, d1, d2, xh, S, sg)
                if right:
                    M3 = frame(M, Q - M, Cr - M)
                    M2 = frame(v3(Mp), v3(Qp - Mp), v3(Crp - Mp))
                else:
                    M3 = frame(C, Q - C, M - C)
                    M2 = frame(v3(Cp), v3(Qp - Cp), v3(Mp - Cp))
                return M3 @ M2.inverted()

            nm = "Front" if end == "F" else "Back"
            hl = self.add(Panel(f"{piece}.{end}L", piece, "panel",
                                [[tuple(Cp), tuple(Qp), tuple(Mp)]], asm_half, PL.name, None,
                                f"{lab}: {nm.lower()} left"))
            hl.hinge = self._hinge_on(PL.name, asm_half, tuple(Qp), tuple(Cp))
            asm_r = (lambda t, f=asm_half: f(t, right=True))
            hr = self.add(Panel(f"{piece}.{end}R", piece, "panel",
                                [[tuple(Qp), tuple(Mp), tuple(Crp)]], asm_r, hl.name, None,
                                f"{lab}: {nm.lower()} right"))
            hr.hinge = self._hinge_on(hl.name, asm_r, tuple(Mp), tuple(Qp))
            ends.append((end, hr, Qp, Crp, Mp, yc, yq))

        # glue tabs: each end's right half onto the right slope (underneath)
        def unit(x, y):
            n = math.hypot(x, y)
            return x / n, y / n

        for end, hr, Qp, Crp, Mp, yc, yq in ends:
            Qp, Crp, Mp = tuple(map(float, Qp)), tuple(map(float, Crp)), tuple(map(float, Mp))
            e_ = unit(Crp[0] - Qp[0], Crp[1] - Qp[1])
            n_ = (-e_[1], e_[0])
            if n_[0] * (Mp[0] - Qp[0]) + n_[1] * (Mp[1] - Qp[1]) > 0:
                n_ = (-n_[0], -n_[1])
            L_ = math.hypot(Crp[0] - Qp[0], Crp[1] - Qp[1])
            w = min(tb, 0.4 * L_)
            ch = 0.6 * w
            tab = [Qp, Crp, (Crp[0] + w * n_[0] - ch * e_[0], Crp[1] + w * n_[1] - ch * e_[1]),
                   (Qp[0] + w * n_[0] + ch * e_[0], Qp[1] + w * n_[1] + ch * e_[1])]
            # on the right slope: Q at (0, yq), C at (h, yc), interior towards the side
            Qs, Cs = (0.0, yq), (h, yc)
            es = unit(Cs[0] - Qs[0], Cs[1] - Qs[1])
            ns = (-es[1], es[0])
            if ns[0] * 0.6 * h + ns[1] * (y0 + 0.5 * D - yq) < 0:
                ns = (-ns[0], -ns[1])

            def to_s(q):  # net -> right slope pattern (folded under, along the edge)
                al = (q[0] - Qp[0]) * e_[0] + (q[1] - Qp[1]) * e_[1]
                be = (q[0] - Qp[0]) * n_[0] + (q[1] - Qp[1]) * n_[1]
                return (Qs[0] + al * es[0] + be * ns[0], Qs[1] + al * es[1] + be * ns[1])

            def to_p(q):
                al = (q[0] - Qs[0]) * es[0] + (q[1] - Qs[1]) * es[1]
                be = (q[0] - Qs[0]) * ns[0] + (q[1] - Qs[1]) * ns[1]
                return (Qp[0] + al * e_[0] + be * n_[0], Qp[1] + al * e_[1] + be * n_[1])

            # keep it on the slope (a pyramid's sides are triangles)
            on = [to_s(q) for q in tab]
            for n2, d2 in halfplanes(ccw(PR.polys[0])):
                if abs(n2[0] * Qs[0] + n2[1] * Qs[1] - d2) < 1e-6 and \
                        abs(n2[0] * Cs[0] + n2[1] * Cs[1] - d2) < 1e-6:
                    continue  # the edge it is glued along
                on = clip_halfplane(on, n2, d2 + 0.3)
                if len(on) < 3:
                    break
            if len(on) < 3:
                continue
            # front and back tabs share the slope: split it between them
            m0, m1 = (0.0, 0.5 * (yr1 + yr2)), (h, y0 + 0.5 * D)
            nx, ny = -(m1[1] - m0[1]), m1[0] - m0[0]
            if nx * Cs[0] + ny * Cs[1] < nx * m0[0] + ny * m0[1]:
                nx, ny = -nx, -ny
            on = clip_halfplane(on, (nx, ny), nx * m0[0] + ny * m0[1] + 0.5 * math.hypot(nx, ny))
            if len(on) < 3:
                continue
            tab = [to_p(q) for q in on]
            # and clear of the right slope where they sit side by side in the net
            tab = clip_halfplane(tab, (-ns[0], -ns[1]), -(ns[0] * Qs[0] + ns[1] * Qs[1]) + 0.3)
            if len(tab) < 3 or abs(poly_area(tab)) < 2.0:
                continue
            Fp = frame(v3(Qp), v3(e_), v3(n_))
            Fs = frame(v3(Qs), v3(es), v3(ns))
            A = Matrix.Translation((0, 0, -TAB_LIFT)) @ Fs @ Fp.inverted()
            self.add(Panel(f"{piece}.{end}Tab", piece, "tab", [tab],
                           (lambda t, A=A: asm_R(t) @ A), PR.name, None, f"{lab}: end glue tab"))

        # base tabs: on the strips, or inside the tube's side walls
        for side, poly_x, sgn, par in (("L", -h, -1.0, parL), ("R", h, 1.0, parR)):
            c2 = min(0.3 * tb, 0.2 * D)
            poly = [(poly_x, y0), (poly_x + sgn * tb, y0 + c2),
                    (poly_x + sgn * tb, y0 + D - c2), (poly_x, y0 + D)]
            if walls is not None and side == "L":
                # clear of the tube's closing tab, glued inside the same wall
                poly = clip_halfplane(poly, (0.0, -1.0), -(y0 + D - tb - 0.5))
            if walls is None:
                k = 1.0 if tab_side == "IN" else -1.0
                if k > 0:  # keep clear of the fold
                    lim = a - 0.5
                    poly = clip_halfplane(poly, (-sgn, 0.0), -(h + lim)) if sgn > 0 else \
                        clip_halfplane(poly, (1.0, 0.0), -h - lim)
                Tp = host.T1 if side == "L" else host.T2
                T = frame(Vector((sgn * (a + k * h), 0.0, TAB_LIFT)), (-k, 0, 0), (0, 1, 0))
                pa_ = self.panels[par].asm
                Tpat = Tp @ T
                asm_t = (lambda t, pa=pa_, T=Tpat: pa(t) @ T)
            else:
                # the wall's own pattern: u along it from back to front (left)
                # or front to back (right), v up; the tab hangs down inside
                wall = self.panels[par]
                tr = self.t_ref
                Rel = wall.asm(tr).inverted() @ (asm_L if side == "L" else asm_R)(tr)
                p0, p1 = Rel @ v3((poly_x, y0)), Rel @ v3((poly_x, y0 + D))
                ew = (p1 - p0).normalized()
                Fs = frame(p0, ew, (0.0, -1.0, 0.0))  # down the wall
                Fp = frame(v3((poly_x, y0)), (0.0, 1.0, 0.0), (sgn, 0.0, 0.0))
                Tpat = Matrix.Translation((0, 0, -TAB_LIFT)) @ Fs @ Fp.inverted()
                pa_ = wall.asm
                asm_t = (lambda t, pa=pa_, T=Tpat: pa(t) @ T)
            self.add(Panel(f"{piece}.Tab{side}", piece, "tab", [poly], asm_t, par, None,
                           f"{lab}: base tab {side}"))

    def _tether(self, m):
        """Wall joining a tube's corner or crease to another tube's, or to a
        small foot glued on a strip. Straight if its ends stay the same
        distance apart; otherwise it gets a vertical crease and is long
        enough for the farthest the ends get apart (plus Slack)."""
        uid, lab = m["uid"], m["label"]
        A_uid, A_pt = int(m["from_uid"]), m.get("from_pt", "FL")
        TA = self.tubes.get(A_uid)
        if TA is None:
            self.warn(f"{lab}: its tube was skipped; skipped too")
            return
        host, a = TA["host"], TA["a"]
        to = m.get("to", "LEFT")
        hgt = float(m.get("height", TA["h"]))
        tb = min(float(m.get("tab", 10.0)), 20.0)
        kf = float(m.get("foot", 12.0))
        piece = f"Tether{uid}"
        self.add_piece(Piece(piece, lab, 1 + uid, (40.0, 0.5 * hgt)))

        if to == "TUBE":
            TB = self.tubes.get(int(m["to_uid"]))
            if TB is None:
                self.warn(f"{lab}: its second tube was skipped; skipped too")
                return
            if abs(TB["a"] - a) > 1e-6:
                self.warn(f"{lab}: joined tubes must use the same Strip Distance (the walls "
                          f"would have to slide); skipped")
                return
            B_uid, B_pt = int(m["to_uid"]), m.get("to_pt", "FR")

            def endB(t):
                return self.tube_plan(B_uid, t)[B_pt]
        else:
            sgnx = -1.0 if to == "LEFT" else 1.0
            yb = float(m.get("to_y", 100.0))

            def endB(t):
                S, e, xh, Y, sn, cs = self.strip_frame(host, t)
                return (sgnx * a * sn, yb)

        def endA(t):
            return self.tube_plan(A_uid, t)[A_pt]

        def dist(t):
            pa, pb = endA(t), endB(t)
            return math.hypot(pb[0] - pa[0], pb[1] - pa[1])

        ds = [dist(t) for t in self.TABLE_T]
        dmin, dmax, d0 = min(ds), max(ds), ds[0]
        if dmax < 1.0:
            self.warn(f"{lab}: its ends meet; skipped")
            return

        # ends may meet as the card shuts (like a tube's own front pair), but
        # must not run into each other part way open
        dips = [ds[i] for i in range(1, len(ds) - 1)
                if ds[i] <= ds[i - 1] and ds[i] <= ds[i + 1] and self.TABLE_T[i] > 1.0]
        if dips and min(dips) < 2.0:
            self.warn(f"{lab}: its two ends pass through each other as the card opens; "
                      f"skipped (join points that stay apart)")
            return
        straight = dmax - dmin < 0.05 and float(m.get("slack", 0.0)) <= 0.0
        # A creased tether has to lie flat when the card shuts, so its halves
        # differ by exactly the closed distance between its ends (it folds
        # back on itself there), and together reach the farthest the ends get
        # apart, plus slack (half a millimetre at least, or it binds).
        L = dmax + (0.0 if straight else max(float(m.get("slack", 0.0)), 0.5))

        def lead_dir():
            # direction the ends approach each other from as the card shuts
            for tt in (2.0, 5.0, 10.0, 30.0, 90.0):
                pa, pb = endA(tt), endB(tt)
                dd = math.hypot(pb[0] - pa[0], pb[1] - pa[1])
                if dd > 0.05:
                    return ((pb[0] - pa[0]) / dd, (pb[1] - pa[1]) / dd)
            return (1.0, 0.0)

        u_near = lead_dir()
        if not straight and d0 < 0.5:
            # The ends meet as the card shuts. That folds flat only if they
            # come together across the fold (like a tube's front pair: the
            # crease then lies along the fold); head-on along it, the tether
            # would have to snap over.
            if abs(u_near[0]) < 0.7:
                self.warn(f"{lab}: its ends meet head-on along the fold as the card shuts, "
                          f"so it can't fold flat; move one end")
                return
            d0 = 0.0
        if not straight and dmin < d0 - 0.3:
            self.warn(f"{lab}: its ends come closer together as the card starts to open than "
                      f"when it is shut, so it can't both fold flat and reach; move one end")
            return
        d0 = min(d0, dmin)
        # When shut it folds back on itself past one end; pick the end that
        # keeps that fold on the card (nearest the middle).
        pa0, pb0 = endA(T_MIN), endB(T_MIN)
        past = []
        for longA in (True, False):
            la, lb = (0.5 * (L + d0), 0.5 * (L - d0)) if longA else (0.5 * (L - d0), 0.5 * (L + d0))
            ux, uy = u_near
            cy = pa0[1] + (la if longA else -la) * uy
            past.append((abs(cy - 0.5 * self.H), la, lb))
        _, L1, L2 = min(past)

        def crease(t, side):
            pa, pb = endA(t), endB(t)
            dx, dy = pb[0] - pa[0], pb[1] - pa[1]
            d = math.hypot(dx, dy)
            if d < 0.05:  # ends (nearly) together: use the way they approach
                ux, uy = u_near
                d = max(d, 1e-9)
            else:
                ux, uy = dx / d, dy / d
            ca = max(-1.0, min(1.0, (L1 * L1 + d * d - L2 * L2) / (2 * L1 * d)))
            sa = math.sqrt(1 - ca * ca) * side
            return (pa[0] + L1 * (ca * ux - sa * uy), pa[1] + L1 * (ca * uy + sa * ux))

        def poke(side):
            worst = 0.0
            for t in self.TABLE_T[::5]:
                S, e, xh, Y, sn, cs = self.strip_frame(host, t)
                worst = max(worst, abs(crease(t, side)[0]) - a * sn)
            return worst

        bend = m.get("bend", "AUTO")
        if straight:
            side = 1.0
        elif bend == "AUTO":
            side = min((1.0, -1.0), key=poke)
        else:
            want = -1.0 if bend == "FRONT" else 1.0  # front = towards smaller y
            side = max((1.0, -1.0), key=lambda sd: want * (crease(90.0, sd)[1] -
                                                           0.5 * (endA(90.0)[1] + endB(90.0)[1])))
        if not straight and poke(side) > 0.5:
            self.warn(f"{lab}: its crease swings outside the strips, so it would pass under "
                      f"the pages; try the other Bend or move its ends")

        def plan(t):
            out = dict(A=endA(t), B=endB(t))
            if not straight:
                out["C"] = crease(t, side)
            return out

        if straight:
            segs = [("W1", "A", "B", 0.0, dmax)]
        else:
            segs = [("W1", "A", "C", 0.0, L1), ("W2", "C", "B", L1, L1 + L2)]
        Ltot = segs[-1][4]
        att_wall, att_toward = TA["attach"][A_pt]
        prev = None
        for i, (nm, p0, p1, u0, u1) in enumerate(segs):
            poly = [(u0, 0), (u1, 0), (u1, hgt), (u0, hgt)]
            asm = self._wall_asm(host, a, p0, p1, u0, plan)
            parent = att_wall if prev is None else prev.name
            if prev is None:
                # hinge on the tube wall's vertical edge at point A
                Tu = self._tube_u(A_uid, A_pt, att_wall)
                Hp = hinge_frame_2d((Tu, 0), (0, 1))
            else:
                Hp = hinge_frame_2d((u0, 0), (0, 1))
            prev = self.add(Panel(f"{piece}.{nm}", piece, "panel", [poly], asm, parent,
                                  Hinge(Hp, hinge_frame_2d((u0, 0), (0, 1)), "TABLE", {}),
                                  f"{lab}: wall {i + 1}"))
        # glue tab at A, on the outside of the tube wall
        A_wall_other = att_toward

        def asm_tabA(t):
            p = self.tube_plan(A_uid, t)
            S, e, xh, Y, sn, cs = self.strip_frame(host, t)
            a3 = self.plan3d(host, a, t, p[A_pt])
            o3 = self.plan3d(host, a, t, p[A_wall_other])
            Mw = self.panels[att_wall].asm(t)
            nout = Mw.to_3x3() @ Z
            return frame(a3 + TAB_LIFT * nout, (a3 - o3).normalized(), e)

        tabA = [(-tb, min(0.2 * hgt, 0.3 * tb)), (0, 0), (0, hgt), (-tb, hgt - min(0.2 * hgt, 0.3 * tb))]
        self.add(Panel(f"{piece}.TabA", piece, "tab", [tabA], asm_tabA, att_wall, None,
                       f"{lab}: glue tab"))
        if to == "TUBE":
            Bw, Btoward = self.tubes[int(m["to_uid"])]["attach"][m.get("to_pt", "FR")]
            B_uid_, B_pt_ = int(m["to_uid"]), m.get("to_pt", "FR")

            def asm_tabB(t):
                p = self.tube_plan(B_uid_, t)
                b3 = self.plan3d(host, a, t, p[B_pt_])
                o3 = self.plan3d(host, a, t, p[Btoward])
                S, e, xh, Y, sn, cs = self.strip_frame(host, t)
                nout = self.panels[Bw].asm(t).to_3x3() @ Z
                return frame(b3 + TAB_LIFT * nout, (o3 - b3).normalized(), e) \
                    @ frame(Vector((Ltot, 0, 0)), (1, 0, 0), (0, 1, 0)).inverted()

            tabB = [(Ltot, 0), (Ltot + tb, min(0.2 * hgt, 0.3 * tb)),
                    (Ltot + tb, hgt - min(0.2 * hgt, 0.3 * tb)), (Ltot, hgt)]
            self.add(Panel(f"{piece}.TabB", piece, "tab", [tabB], asm_tabB, Bw, None,
                           f"{lab}: glue tab"))
        else:
            # a short foot standing on the strip, glued down by a base tab
            yb = float(m.get("to_y", 100.0))
            last = self.panels[f"{piece}.{segs[-1][0]}"]
            pA0 = endA(180.0)
            fdir = 1.0 if yb >= pA0[1] else -1.0  # foot runs on away from the tube

            def foot_pts(t):
                pb = endB(t)
                return dict(B=pb, E=(pb[0], pb[1] + fdir * kf))

            fasm = self._wall_asm(host, a, "B", "E", Ltot, foot_pts)
            sgnx = -1.0 if to == "LEFT" else 1.0
            pg, Tp = (host.p1, host.T1) if to == "LEFT" else (host.p2, host.T2)
            foot = self.add(Panel(f"{piece}.Foot", piece, "panel",
                                  [[(Ltot, 0), (Ltot + kf, 0), (Ltot + kf, hgt), (Ltot, hgt)]],
                                  fasm, pg,
                                  Hinge(Tp @ hinge_frame_2d((sgnx * a, yb), (0, fdir)),
                                        hinge_frame_2d((Ltot, 0), (1, 0))),
                                  f"{lab}: foot"))
            # re-parent the last wall onto the foot: the chain is page -> foot -> walls
            last.parent = foot.name
            last.hinge = Hinge(hinge_frame_2d((Ltot, 0), (0, 1)),
                               hinge_frame_2d((Ltot, 0), (0, 1)), "TABLE", {})
            # base tab under the foot, folded away from the tether
            kk = 1.0 if m.get("tab_side", "IN") == "IN" else -1.0
            # strip pattern +v -> across the strip, so the tab (v < 0) folds
            # towards the fold for IN, away for OUT
            T = frame(Vector((sgnx * a, yb, TAB_LIFT)), (0, fdir, 0), (sgnx * kk, 0, 0)) \
                @ frame(Vector((Ltot, 0, 0)), (1, 0, 0), (0, 1, 0)).inverted()
            c2 = min(0.3 * tb, 0.2 * kf)
            poly = [(Ltot + c2, -tb), (Ltot, 0), (Ltot + kf, 0), (Ltot + kf - c2, -tb)]
            pa_ = self.panels[pg].asm
            Tpat = Tp @ T
            self.add(Panel(f"{piece}.FootTab", piece, "tab", [poly],
                           (lambda t, pa=pa_, T=Tpat: pa(t) @ T), pg, None, f"{lab}: foot tab"))
            # the chain must be parent-first: move the walls after the foot
            for nm, *_ in segs[::-1]:
                n_ = f"{piece}.{nm}"
                self.order.remove(n_)
                self.order.insert(self.order.index(foot.name) + 1, n_)
            # walls now hang from the foot: W2 <- foot, W1 <- W2
            if not straight:
                w1 = self.panels[f"{piece}.W1"]
                w1.parent = last.name
                w1.hinge = Hinge(hinge_frame_2d((L1, 0), (0, 1)), hinge_frame_2d((L1, 0), (0, 1)),
                                 "TABLE", {})
                self.order.remove(w1.name)
                self.order.insert(self.order.index(last.name) + 1, w1.name)
        self.tethers[uid] = dict(straight=straight, length=L)

    def _tube_u(self, uid, pt, wall):
        """Pattern u of a tube point on the given tube wall."""
        T = self.tubes[uid]
        D, wf, wb = T["D"], T["wf"], T["wb"]
        u = {"FL_": {"BL": 0.0, "FL": D}, "FR_": {"FR": D + 2 * wf, "BR": 2 * D + 2 * wf},
             "GFL": {"FL": D, "CF": D + wf}, "GBR": {"BR": 2 * D + 2 * wf, "CB": 2 * D + 2 * wf + wb}}
        return u[wall.split(".")[-1]][pt]

    # ------------------------------------------------------------------ flap
    def _flap(self, m):
        """Pull-tab flap on a page. The flap is glued down along its hinge by a
        tab. A strip glued under the flap runs back through a slit in the page
        and under it to the card edge; pulling it shortens the part above
        the page, which lifts the flap; it swings over towards the pull."""
        uid, lab = m["uid"], m["label"]
        W, H = self.W, self.H
        left = m.get("side", "R") == "L"
        page = "Page.L" if left else "Page.R"
        hx = -float(m["x"]) if left else float(m["x"])
        hy = float(m["y"])
        uu = {"TOP": (0, -1), "BOTTOM": (0, 1), "LEFT": (1, 0), "RIGHT": (-1, 0)}[m.get("hinge", "TOP")]
        U = Vector((uu[0], uu[1], 0))
        Hd = Z.cross(U)
        Wf, Lf = float(m["width"]), float(m["length"])
        tb = min(float(m.get("tab", 10.0)), 30.0)
        amax = float(m.get("angle", 150.0))
        ws = min(float(m.get("strip", 10.0)), Wf - 2)
        g = max(3.0, min(float(m.get("glue_at", 0.5 * Lf)), Lf - 2))
        gap = float(m.get("gap", 4.0))
        sl = tb + gap  # slit distance behind the hinge
        gl = min(10.0, Lf - g + 0.0, 0.5 * g) if Lf - g > 1 else 1.0
        pdir = -U  # the flap swings over towards the pull
        H3 = Vector((hx, hy, 0.0))
        S3 = H3 - sl * U

        def on_page(pt):
            x0, x1 = (-W, 0.0) if left else (0.0, W)
            return x0 - 1e-6 <= pt.x <= x1 + 1e-6 and -1e-6 <= pt.y <= H + 1e-6

        corners = [H3 + a * U + b * Hd for a in (-tb, Lf) for b in (-Wf / 2, Wf / 2)]
        if not all(on_page(c) for c in corners):
            self.warn(f"{lab}: the flap runs off its page")
        # distance from the slit to the page edge along the pull direction
        x0, x1 = (-W, 0.0) if left else (0.0, W)
        dists = []
        for axis, lo, hi in ((0, x0, x1), (1, 0.0, H)):
            dv = pdir[axis]
            if abs(dv) > 1e-9:
                for edge in (lo, hi):
                    tt = (edge - S3[axis]) / dv
                    if tt > 0:
                        dists.append((tt, axis, edge))
        tt, axis, edge = min(dists)
        if axis == 0 and abs(edge) < 1e-9:
            self.warn(f"{lab}: the pull strip would run across the spine; turn the flap "
                      f"or swap Pull so it exits an outer edge")
        out = float(m.get("pull_out", 30.0))
        Lu = tt + out
        A = math.radians(amax)

        pf, ps = f"Flap{uid}", f"Pull{uid}"
        self.add_piece(Piece(pf, lab, 1 + uid, (0.5 * Lf, 0.0)))
        self.add_piece(Piece(ps, f"{lab} strip", 500 + uid, (0.5 * Lu, 0.0)))
        self.pull.setdefault(uid, 0.0)
        pa = self.panels[page].asm

        def theta():
            return A * max(0.0, min(1.0, self.pull.get(uid, 0.0)))

        def fdir(th):
            return math.cos(th) * U + math.sin(th) * Z

        flap_poly = [(0, -Wf / 2), (Lf, -Wf / 2), (Lf, Wf / 2), (0, Wf / 2)]
        ch = min(0.3 * tb, 0.2 * Wf)
        tab_poly = [(-tb, -Wf / 2 + ch), (0, -Wf / 2), (0, Wf / 2), (-tb, Wf / 2 - ch)]
        Tt = frame(H3 + TAB_LIFT * Z, U, Hd)
        tab = self.add(Panel(f"{pf}.Tab", pf, "tab", [tab_poly], lambda t: pa(t) @ Tt, page,
                             None, f"{lab}: hinge tab"))

        def asm_flap(t):
            return pa(t) @ frame(H3 + TAB_LIFT * Z, fdir(theta()), Hd)

        hf = hinge_frame_2d((0, 0), (0, 1))
        flap = self.add(Panel(f"{pf}.Flap", pf, "panel", [flap_poly], asm_flap, tab.name,
                              Hinge(hf, hf, "PULL", dict(var="p", uid=uid,
                                                         fn=lambda q: A * q,
                                                         expr=f"radians({amax:.6g}*p)")),
                              f"{lab}: flap"))

        # the strip: glue end under the flap | link to the slit | under the page
        eps = 2 * TAB_LIFT
        glue_poly = [(-gl, -ws / 2), (0, -ws / 2), (0, ws / 2), (-gl, ws / 2)]

        zl = TAB_LIFT

        def Gs(th):
            """Glue point under the flap (just below its surface), in page coords."""
            f = fdir(th)
            nf = f.cross(Hd)
            return H3 + zl * Z + g * f - eps * nf

        def vparts(th):
            # S - G in (U, Z) components
            c_, s_ = math.cos(th), math.sin(th)
            return (-sl - g * c_ - eps * s_, -zl - g * s_ + eps * c_)

        Lk = math.hypot(*vparts(0.0))
        link_poly = [(0, -ws / 2), (Lk, -ws / 2), (Lk, ws / 2), (0, ws / 2)]
        under_poly = [(Lk, -ws / 2), (Lk + Lu, -ws / 2), (Lk + Lu, ws / 2), (Lk, ws / 2)]

        def asm_glue(t):
            th = theta()
            return pa(t) @ frame(Gs(th), -fdir(th), Hd)

        def asm_link(t):
            th = theta()
            return pa(t) @ frame(Gs(th), (S3 - Gs(th)).normalized(), Hd)

        def d_of(q):
            return Lk - math.hypot(*vparts(A * q))

        Mu0 = frame(S3 - eps * Z, pdir, Hd) @ Matrix.Translation((-Lk, 0, 0))

        def asm_under(t):
            q = max(0.0, min(1.0, self.pull.get(uid, 0.0)))
            return pa(t) @ Matrix.Translation(d_of(q) * pdir) @ Mu0

        glue = self.add(Panel(f"{ps}.Glue", ps, "tab", [glue_poly], asm_glue, flap.name, None,
                              f"{lab}: strip glue end"))
        T = f"radians({amax:.6g}*p)"
        fn_link = (lambda q: math.atan2(vparts(A * q)[1], vparts(A * q)[0]) - A * q)
        ex_link = (f"atan2({-zl:.6g}-{g:.6g}*sin({T})+{eps:.6g}*cos({T}),"
                   f"{-sl:.6g}-{g:.6g}*cos({T})-{eps:.6g}*sin({T}))-{T}")
        hl = hinge_frame_2d((0, 0), (0, 1))
        link = self.add(Panel(f"{ps}.Link", ps, "panel", [link_poly], asm_link, glue.name,
                              Hinge(hl, hl, "PULL", dict(var="p", uid=uid, fn=fn_link, expr=ex_link)),
                              f"{lab}: strip"))
        Fc = frame(Vector((Lk, 0, 0)), (0, -1, 0), (1, 0, 0))
        Hp = Mu0 @ Fc
        # |S - G|^2 = K0 + Kc cos(th) + Ks sin(th)
        K0 = sl * sl + g * g + eps * eps + zl * zl
        Kc = 2 * sl * g - 2 * zl * eps
        Ks = 2 * sl * eps + 2 * zl * g
        ex_d = f"{Lk:.9g}-sqrt({K0:.9g}{Kc:+.9g}*cos({T}){Ks:+.9g}*sin({T}))"
        under = self.add(Panel(f"{ps}.Under", ps, "panel", [under_poly], asm_under, page,
                               Hinge(Hp, Fc, "SLIDE", dict(var="p", uid=uid, fn=d_of, expr=ex_d)),
                               f"{lab}: pull tab"))
        under.outside = True
        self.soft.add(frozenset((link.name, under.name)))
        # slit in the page where the strip comes through
        slot = [S3 + a * U + b * Hd for a, b in ((-0.6, -ws / 2 - 1), (0.6, -ws / 2 - 1),
                                                 (0.6, ws / 2 + 1), (-0.6, ws / 2 + 1))]
        self.carve("Card", [tuple(v[:2]) for v in slot], {page}, lab)
        dmax = d_of(1.0)
        if dmax > out - 3:
            self.warn(f"{lab}: pulling {dmax:.0f} mm needs a longer Pull Tab "
                      f"(it would vanish into the card)")
        self.flaps[uid] = dict(label=lab, travel=dmax)

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
        v = host.v1
        left = self.carve(piece, [v(0, y0 - b), v(0, y0 + a), v(-Lj, y0)], {host.p1}, lab)
        if left is None:
            return
        right = self.carve(piece, [v(0, y0 - b), v(Lj, y0), v(0, y0 + a)], {host.p2}, lab)
        if right is None:
            self.warn(f"{lab}: the right half does not fit; the cut is incomplete")
            return
        ny = host.d1(0.0, 1.0)
        p0 = v(0.0, y0)
        ul, ll = self.split_cells(left, ny, ny[0] * p0[0] + ny[1] * p0[1])
        ur, lr = self.split_cells(right, ny, ny[0] * p0[0] + ny[1] * p0[1])
        base = f"Mouth{uid}"
        for jaw, yP, gL, gR, cp, cl, cr, name in (
            ("U", y0 + a, unit2(-Lj, -a), unit2(Lj, -a), (0, -1), ul, ur, "upper jaw"),
            ("D", y0 - b, unit2(-Lj, b), unit2(Lj, b), (0, 1), ll, lr, "lower jaw"),
        ):
            key = f"{base}.{jaw}"
            alpha = math.acos(max(-1.0, min(1.0, gL[0] * cp[0] + gL[1] * cp[1])))
            self.joints[key] = dict(host=host, y=yP, uL=gL, uR=gR, aL=alpha, aR=alpha)
            P = v(0.0, yP)
            d = host.d1
            self._half(f"{key}L", piece, cl, P, d(*gL), d(*cp), "L", key, f"{lab}: {name} left")
            self._half(f"{key}R", piece, cr, P, d(*gR), d(*cp), "R", key, f"{lab}: {name} right")
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
        # mathutils works in single precision: half a micron of slack
        if not is_roty(M, 5e-4):
            raise ValueError(f"{name}: fold is not a pure hinge at t={t}")
        return angle_from_roty(M)

    def true_slide(self, name, t):
        p = self.panels[name]
        h = p.hinge
        M = h.Hp.inverted() @ self.rel(name, t) @ h.Fc
        tr = M.to_translation()
        if not is_roty(M.to_3x3().to_4x4(), 1e-4) or abs(angle_from_roty(M)) > 1e-4 \
                or abs(tr.x) > 1e-3 or abs(tr.z) > 1e-3:
            raise ValueError(f"{name}: not a pure slide")
        return tr.y

    TABLE_T = [T_MIN] + [float(d) for d in range(1, 181)]

    def _table_hinge(self, name, h, tol=2e-4):
        """Hinges with no short formula: the solved angle, sampled every
        degree and more finely wherever the curve bends sharply (a crease
        pulling straight), written into the rig as a driver curve."""
        def wrap(d):
            return (d + math.pi) % (2 * math.pi) - math.pi

        cache = {}
        bad = []

        def true(t):
            if t not in cache:
                try:
                    cache[t] = self.true_psi(name, t)
                except ValueError:
                    # the host can't hold this pose (paper would tear there):
                    # follow it as best we can and say so
                    p = self.panels[name]
                    M = h.Hp.inverted() @ self.rel(name, t) @ h.Fc
                    cache[t] = angle_from_roty(M)
                    bad.append(t)
            return cache[t]

        pts = list(self.TABLE_T)
        # extra folds and things on uneven hosts: refine less finely, and stop
        # (with a warning) rather than chase a kink forever
        loose = getattr(h, "corner_ok", False) or getattr(h, "host_bound", False)
        floor = 1.0 / 64 if loose else 1.0 / 512
        budget = 3000 if loose else 10 ** 9
        out = [pts[0]]
        for i in range(len(pts) - 1):
            stack = [(pts[i], pts[i + 1])]
            seg = []
            while stack:
                t0, t1 = stack.pop()
                tm = 0.5 * (t0 + t1)
                v0, v1, vm = true(t0), true(t1), true(tm)
                lin = v0 + 0.5 * wrap(v1 - v0)
                if abs(wrap(vm - lin)) > tol and t1 - t0 > floor and len(cache) < budget:
                    stack.append((tm, t1))
                    stack.append((t0, tm))
                else:
                    seg.append(t1)
            out += seg
        T, V, prev = [], [], None
        for t in sorted(set(out)):
            v = true(t)
            if prev is not None:
                v = prev + wrap(v - prev)
            T.append(t)
            V.append(v)
            prev = v
        h.table = list(zip(T, V))
        import bisect

        def fn(t, T=T, V=V):
            t = max(T[0], min(T[-1], t))
            i = max(0, min(len(T) - 2, bisect.bisect_right(T, t) - 1))
            f = (t - T[i]) / (T[i + 1] - T[i])
            return V[i] + f * (V[i + 1] - V[i])

        h.fn = fn
        h.expr = None
        err = 0.0
        for i in range(len(T) - 1):
            tm = 0.5 * (T[i] + T[i + 1])
            if self.tmax < 180.0 and tm > self.tmax - 0.5:
                continue  # a floor pulling flat at full opening: square-root corner
            if getattr(h, "corner_ok", False) and (tm > self.tmax - 1.5 or tm < 1.5):
                continue  # extra folds pulling flat as the card opens flat or shuts
            err = max(err, abs(wrap(fn(tm) - true(tm))))
        h.check = err
        lab = self.panels[name].label.split(":")[0]
        far = [t for t in bad if t >= 1.0]  # squashed shut: no matter
        if far:
            self.warn(f"{lab}: its fold can't follow the card from about {min(far):.0f} "
                      f"to {max(far):.0f} degrees (the paper would tear)")
        elif err > 2e-3 and not bad:
            if getattr(h, "host_bound", False) or getattr(h, "corner_ok", False):
                self.warn(f"{lab}: moves unevenly (its host fold kinks); check it in "
                          f"the movement test")
            else:
                raise ValueError(f"{name}: tabulated hinge is off by {err:.2e} rad")

    def _expr_hinge(self, name, h):
        """Hinges written as a formula: EXPR (in the open angle T, degrees),
        PULL (rotation in the flap's Pull p) and SLIDE (distance in mm along
        the bone's Y, in p). The formula's sign and constant offset are fitted
        to the solved geometry, then checked."""
        sph = h.sph
        uid = sph.get("uid")
        if sph["var"] == "t":
            pts = [(t, None) for t in self.samples]
        else:
            pts = [(90.0, q) for q in (0.0, 0.15, 0.35, 0.5, 0.65, 0.85, 1.0)]
        rows = []
        for t, q in pts:
            if q is not None:
                self.pull[uid] = q
            true = self.true_slide(name, t) if h.kind == "SLIDE" else self.true_psi(name, t)
            rows.append((true, sph["fn"](t if q is None else q)))
        if uid is not None:
            self.pull[uid] = 0.0
        wrap = (lambda d: d) if h.kind == "SLIDE" else \
            (lambda d: (d + math.pi) % (2 * math.pi) - math.pi)
        best = None
        for sg in ((1.0,) if h.kind == "SLIDE" else (1.0, -1.0)):
            c = rows[0][0] - sg * rows[0][1]
            err = max(abs(wrap(tv - sg * fv - c)) for tv, fv in rows)
            if best is None or err < best[0]:
                best = (err, sg, c)
        err, sg, c = best
        h.expr = f"{c:.9g}{'+' if sg > 0 else '-'}({sph['expr']})"
        h.fn = lambda x, sg=sg, c=c, f=sph["fn"]: c + sg * f(x)
        h.check = err
        tol = 0.02 if h.kind == "SLIDE" else 2e-3
        if err > tol:
            raise ValueError(f"{name}: driver formula is off by {err:.2e}")

    def solve_hinges(self):
        for name in self.order:
            p = self.panels[name]
            h = p.hinge
            if h is None:
                continue
            if h.kind in ("EXPR", "PULL", "SLIDE"):
                self._expr_hinge(name, h)
                continue
            if h.kind == "TABLE":
                self._table_hinge(name, h)
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
                if h.kind == "SPHERICAL" and s > self.tmax - 0.5 and self.tmax < 180.0:
                    continue  # flat at the stage's full opening: a square-root corner
                d = h.fn(s) - self.true_psi(name, s)
                d = (d + math.pi) % (2 * math.pi) - math.pi
                err = max(err, abs(d))
            h.check = err
            if err > 2e-3:  # 0.002 rad: under 0.1 mm on a 50 mm panel
                raise ValueError(f"{name}: driver formula is off by {err:.2e} rad")

    def _valid_samples(self, p):
        """Angles where the paper can actually follow (no tearing)."""
        if p.hinge.kind != "SPHERICAL":
            return self.samples
        key = p.hinge.sph["key"]
        return [s for s in self.samples if self.crease(key, s)[3]]

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

        ok = [x for x in self._valid_samples(p) if x < self.tmax - 1.0] or [180.0]
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

    # ------------------------------------------------------------- display
    LIFT_FROM, LIFT_SPAN = 60.0, 50.0  # degrees before full open; see build.lift

    def lift_fraction(self, t):
        return max(0.0, min(1.0, (t - (self.tmax - self.LIFT_FROM)) / self.LIFT_SPAN))

    def shown(self, name, t):
        """Where the rig shows a panel: its pose, plus the lift of anything
        it hangs from that is raised onto its tabs near flat (display only)."""
        M = self.panels[name].asm(t)
        off = Vector((0.0, 0.0, 0.0))
        p = self.panels[name]
        while p is not None:
            if p.lift and p.parent:
                n = self.panels[p.parent].asm(t).to_3x3() @ Vector((0.0, 0.0, 1.0))
                off += self.lift_fraction(t) * p.lift * n
            p = self.panels.get(p.parent) if p.parent else None
        return Matrix.Translation(off) @ M

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
            if p.kind == "page" or p.outside:
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
                M = host.asm(self.t_ref).inverted() @ p.asm(self.t_ref)
                for poly in p.polys:
                    q = [(M @ v3(c)).to_2d()[:] for c in poly]
                    # which face of the host it is glued to (printed or back)
                    face = 1 if (M @ v3(poly[0])).z >= 0 else -1
                    prints.setdefault(host.piece, []).append((lab, "tab", q, host, face))
            elif name in self.cut_panels:
                for poly in p.polys:
                    prints.setdefault(p.piece, []).append((lab, "cut", poly, p, 0))
        for piece, items in prints.items():
            for i, (la, ka, pa, ha, fa) in enumerate(items):
                if ka == "tab":
                    on = sum(self._overlap(pa, q) for q in ha.polys)
                    if on < abs(poly_area(pa)) - 1.0:
                        self.warn(f"{la}: a glue tab hangs off {ha.label.split(':')[0]}")
                for lb, kb, pb, hb, fb in items[i + 1:]:
                    if {ka, kb} == {"tab", "cut"} and (ha if ka == "tab" else hb) is \
                            (hb if ka == "tab" else ha):
                        continue  # a tab glued onto that very cut-in panel
                    if ka == kb == "tab" and fa != fb:
                        continue  # glued to opposite faces of the paper
                    if la != lb and frozenset((la, lb)) not in self.stack_ok and \
                            self._overlap(pa, pb) > 1.0:
                        self.warn(f"{la} and {lb} overlap on the paper")

    def check_fit(self):
        """Panels must stay between the pages and inside the card outline."""
        self.check_overlaps()
        W, H = self.W, self.H
        for name in self.order:
            p = self.panels[name]
            if p.kind != "panel" or p.outside:
                continue
            lab = p.label.split(":")[0]
            pts = [v3(q) for poly in p.polys for q in poly]
            poke = None
            for t in self.samples:
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
