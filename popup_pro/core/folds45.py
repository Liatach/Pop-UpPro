"""45 degree folds (Birmingham 77-81): the platform, the rising sheet, triangles
in a box's corners, the jack in the box and the double 45."""
import bisect
import math

from mathutils import Matrix, Vector

from .base import halfplanes, Hinge, Host, Panel, Piece, split_convex, T_MIN, TAB_LIFT, unit2
from .geom import ccw, clip_halfplane, frame, hinge_frame_2d, rot_y, v3


class Folds45:
    """45 degree fold builders. Mixed into Model (model.py)."""

    # ------------------------------------------------------- 45 degree folds
    def _brace(self, owner, k, host, y, size, lean, tab, lab, free_y=False):
        """A 45 degree fold (Birmingham 80, 81): a small V-fold in the corner
        between two panels, its glue lines square to their fold and its two
        piece angles 45 degrees. It folds flat as the corner closes and
        stands as a solid gusset when the corner reaches 90 degrees, so it
        props the corner square: the card can't push it any further."""
        g = float(size)
        self._vfold(dict(uid=f"{owner}b{k}", type="VFOLD", label=lab, y=y,
                         phi_l=90.0, phi_r=90.0, alpha_l=45.0, alpha_r=45.0, glue=g,
                         glue_r=g, height=g * math.sqrt(2.0), tab=tab, shape="TRI",
                         # tabs on the brace's own side of its point (its glue lines
                         # are square to the fold, so "inside" is +Y)
                         tab_side="IN" if lean > 0 else "OUT", pref=(0.0, lean),
                         free_y=free_y,  # (its host's own coordinates: no card to be off)
                         slot=500 + 4 * owner + k), host)

    def _bisector(self, host, t):
        """Unit direction halfway between the host's two sides, into its gap
        (well defined from shut to flat)."""
        S, l, r, Y, nl, nr = host.dirs(t)
        s1, s2 = host.lift
        b = l + r + s1 * nl + s2 * nr
        return b.normalized()

    def _platform(self, m, host):
        """Birmingham 80, structural uses of 45 degree folds: a raised platform.
        Two legs glued along strips parallel to the fold (B out on the left,
        C out on the right) carry a top whose two halves meet in a valley
        right above the fold. The legs stay square to the line halfway
        between the pages and each half of the top parallel to its own page,
        so the valley rides at the leg height straight above the fold and B
        and C needn't match: it can stand off the centre. A 45 degree fold
        in each leg's outer corner props it square when the card is flat."""
        uid, lab = m["uid"], m["label"]
        B = float(m["depth"])
        C = float(m.get("depth_r", 0.0) or 0.0) or B
        h, w, y0 = float(m["height"]), float(m["width"]), float(m["y"])
        tb = min(float(m.get("tab", 10.0)), B, C)
        if h < 2.0 or w < 2.0:
            self.warn(f"{lab}: too small to fold")
            return
        if host.is_spine and max(B, C) + h > self.W + 1e-6:
            self.warn(f"{lab}: out + leg height ({max(B, C) + h:.0f} mm) is deeper than the "
                      f"page ({self.W:.0f} mm), so it sticks out when closed")
        if y0 < -1e-6 or y0 + w > self.H + 1e-6:
            self.warn(f"{lab}: runs past the top or bottom of the card")
        base = f"Plat{uid}"
        piece = base
        self.add_piece(Piece(piece, lab, 1 + uid, (h + B, w / 2)))
        lift1, lift2 = host.lift
        U = [0.0, h, h + B, h + B + C, 2 * h + B + C]  # creases along the strip

        def parts(t):
            S, l, r, Y, nl, nr = host.dirs(t)
            b = self._bisector(host, t)
            o = S + y0 * Y
            return o, l, r, Y, nl, nr, b

        def asm_leg_l(t):
            o, l, r, Y, nl, nr, b = parts(t)
            return frame(o + B * l, b, Y)

        def asm_top_l(t):
            o, l, r, Y, nl, nr, b = parts(t)
            return frame(o + B * l + h * b + h * l, -l, Y)

        def asm_top_r(t):
            o, l, r, Y, nl, nr, b = parts(t)
            return frame(o + h * b - (h + B) * r, r, Y)

        def asm_leg_r(t):
            o, l, r, Y, nl, nr, b = parts(t)
            return frame(o + C * r + h * b + U[3] * b, -b, Y)

        def asm_tab_l(t):
            o, l, r, Y, nl, nr, b = parts(t)
            return frame(o + B * l + lift1 * TAB_LIFT * nl, l, Y)

        def asm_tab_r(t):
            o, l, r, Y, nl, nr, b = parts(t)
            return frame(o + C * r + U[4] * r + lift2 * TAB_LIFT * nr, -r, Y)

        ch = min(0.3 * tb, 0.25 * w)
        strip = [[(U[j], 0), (U[j + 1], 0), (U[j + 1], w), (U[j], w)] for j in range(4)]
        tab_l = [(-tb, ch), (0, 0), (0, w), (-tb, w - ch)]
        tab_r = [(U[4], 0), (U[4] + tb, ch), (U[4] + tb, w - ch), (U[4], w)]
        self.add(Panel(f"{base}.TabL", piece, "tab", [tab_l], asm_tab_l, host.p1, None,
                       f"{lab}: tab left"))
        names = ["LegL", "TopL", "TopR", "LegR"]
        texts = ["left leg", "top left", "top right", "right leg"]
        asms = [asm_leg_l, asm_top_l, asm_top_r, asm_leg_r]
        prev = None
        for j in range(4):
            if prev is None:
                hg = Hinge(host.T1 @ hinge_frame_2d((-B, y0), (0, 1)),
                           hinge_frame_2d((0, 0), (0, 1)), "TABLE")
                par = host.p1
            else:
                hg = Hinge(hinge_frame_2d((U[j], 0), (0, 1)),
                           hinge_frame_2d((U[j], 0), (0, 1)), "TABLE")
                par = prev.name
            prev = self.add(Panel(f"{base}.{names[j]}", piece, "panel", [strip[j]], asms[j],
                                  par, hg, f"{lab}: {texts[j]}"))
        self.add(Panel(f"{base}.TabR", piece, "tab", [tab_r], asm_tab_r, host.p2, None,
                       f"{lab}: tab right"))
        self.line_frames[uid] = (piece, lambda q: (q[0] - (h + B), q[1]), (-(h + B), h + C, 0.0, w))
        # its top's valley: a fold opening just like the card, to stand more on
        Tv = Matrix.Translation((h + B, -y0, 0.0))
        hv = Host(self, f"{base}.TopL", 0.0, 0.0, f"{base}.TopR", 0.0, 0.0,
                  f"{lab}: on top", Tv, Tv).finish()
        hv.trig = host.trig
        self.hosts[(uid, "A")] = hv
        # the 45 degree props, one in each leg's outer corner
        brace = m.get("brace", "FRONT")
        if brace == "NONE":
            return
        g = float(m.get("brace_size", 15.0) or 15.0)
        room = min(h, w - 1.0, (self.W - max(B, C)) if host.is_spine else g)
        if g > room + 1e-6:
            g = max(2.0, room)
            self.warn(f"{lab}: 45° folds made {g:.0f} mm to fit the legs and pages")
        tbb = min(float(m.get("tab", 10.0)), 0.5 * g)
        ends = [(y0 + 0.5, 1.0)] + ([(y0 + w - 0.5, -1.0)] if brace == "BOTH" else [])
        corners = (
            ("L", Host(self, host.p1, 0.0, 0.0, f"{base}.LegL", 0.0, 0.0,
                       f"{lab}: left foot", host.T1 @ Matrix.Translation((-B, 0.0, 0.0)),
                       Matrix.Translation((0.0, -y0, 0.0)))),
            ("R", Host(self, f"{base}.LegR", 0.0, 0.0, host.p2, 0.0, 0.0,
                       f"{lab}: right foot", Matrix.Translation((U[4], -y0, 0.0)),
                       host.T2 @ Matrix.Translation((C, 0.0, 0.0)))))
        k = 0
        for side, hf in corners:
            hf.finish()
            hf.trig = False
            for yb, lean in ends:
                n0 = len(self.order)
                self._brace(uid, k, hf, yb, g, lean, tbb,
                            f"{lab}: 45° fold {'left' if side == 'L' else 'right'}"
                            f"{' back' if lean < 0 else ''}")
                for name in self.order[n0:]:
                    hg = self.panels[name].hinge
                    if hg is not None and hg.kind in ("LINEAR", "SPHERICAL", "EXPR"):
                        hg.kind = "TABLE"
                k += 1

    def _riser(self, m, host):
        """Birmingham 81: a single sheet rising from the fold, half way
        between the pages, held up by a 45 degree fold on each face (each
        props its corner square when the card is flat). Its foot is glued
        down by two tabs, one onto each page."""
        uid, lab = m["uid"], m["label"]
        h, w, y0 = float(m["height"]), float(m["width"]), float(m["y"])
        tb = float(m.get("tab", 10.0))
        if host.is_spine and h > self.W + 1e-6:
            self.warn(f"{lab}: taller ({h:.0f} mm) than the page is deep "
                      f"({self.W:.0f} mm), so it sticks out when closed")
        if y0 < -1e-6 or y0 + w > self.H + 1e-6:
            self.warn(f"{lab}: runs past the top or bottom of the card")
        base = f"Rise{uid}"
        piece = base
        self.add_piece(Piece(piece, lab, 1 + uid, (h / 2, w / 2)))
        lift1, lift2 = host.lift

        def asm_sheet(t):
            S, l, r, Y, nl, nr = host.dirs(t)
            return frame(S + y0 * Y, self._bisector(host, t), Y)

        def asm_tab_l(t):
            S, l, r, Y, nl, nr = host.dirs(t)
            return frame(S + y0 * Y + lift1 * TAB_LIFT * nl, -l, Y)

        def asm_tab_r(t):
            S, l, r, Y, nl, nr = host.dirs(t)
            return frame(S + y0 * Y + lift2 * TAB_LIFT * nr, -r, Y)

        slotted = bool(m.get("slotted"))
        g = float(m.get("brace_size", 15.0) or 15.0)
        sheet_polys = [[(0, 0), (h, 0), (h, w), (0, w)]]
        if slotted:
            # Birmingham 81's adaptation: the two 45 degree folds are one
            # piece standing square across the sheet, the two interlocked
            # by slots (2 mm wide) where they cross
            room = min(h, 0.5 * w - 2.0, self.W if host.is_spine else g)
            if g > room + 1e-6:
                g = max(2.0, room)
                self.warn(f"{lab}: 45° folds made {g:.0f} mm to fit the sheet")
            hc = max(g + 2.0, float(m.get("cross_height", 0.0) or 0.0) or 1.5 * h)
            sw = 1.0  # (half the slot's width)
            # where the slots meet, up from the fold: the taller piece is
            # slotted from its foot up to there, the shorter from its top down
            mid = float(m.get("slot_height", 0.0) or 0.0) or min(g, 0.5 * min(h, hc))
            if not 2.0 <= mid <= min(h, hc) - 2.0:
                mid = max(2.0, min(mid, min(h, hc) - 2.0))
                self.warn(f"{lab}: slots meet {mid:.0f} mm up (inside both pieces)")
            s0, s1 = (0.0, mid) if h >= hc else (mid, h)
            # the cross pieces' places along the sheet
            n_x = max(1, min(4, int(m.get("cross_count", 1) or 1)))
            gap = float(m.get("cross_gap", 0.0) or 0.0) or w / n_x
            c0 = 0.5 * w + float(m.get("cross_pos", 0.0) or 0.0)
            yms = [c0 + (k - 0.5 * (n_x - 1)) * gap for k in range(n_x)]
            lo_, hi_ = sw + 2.0, w - sw - 2.0
            if any(not lo_ - 1e-6 <= y_ <= hi_ + 1e-6 for y_ in yms):
                self.warn(f"{lab}: cross pieces kept on the sheet")
                yms = [max(lo_, min(hi_, y_)) for y_ in yms]
            if n_x > 1 and gap < g - 1e-6:
                # (each one's 45° folds lie g along the fold, up one page
                # and down the other)
                self.warn(f"{lab}: cross pieces {gap:.0f} mm apart, so their 45° folds "
                          f"({g:.0f} mm) overlap; space them at least {g:.0f} mm")
            edges = [0.0] + [e for y_ in yms for e in (y_ - sw, y_ + sw)] + [w]
            sheet_polys = [[(0, edges[i]), (h, edges[i]), (h, edges[i + 1]), (0, edges[i + 1])]
                           for i in range(0, len(edges), 2) if edges[i + 1] - edges[i] > 1e-6]
            for y_ in yms:
                for a_, b_ in ((0.0, s0), (s1, h)):
                    if b_ - a_ > 1e-6:
                        sheet_polys.append([(a_, y_ - sw), (b_, y_ - sw), (b_, y_ + sw),
                                            (a_, y_ + sw)])
        sheet = self.add(Panel(f"{base}.Sheet", piece, "panel",
                               sheet_polys, asm_sheet, host.p1,
                               Hinge(host.T1 @ hinge_frame_2d((0.0, y0), (0, 1)),
                                     hinge_frame_2d((0, 0), (0, 1)), "TABLE"),
                               f"{lab}: sheet"))
        if sheet is None:
            return
        ch = min(0.3 * tb, 0.1 * w)
        half = 0.5 * w
        # the foot's tabs: the first half onto the left page, the rest onto
        # the right, with gaps where the sheet is slotted from its foot
        gaps = [(y_ - sw, y_ + sw) for y_ in yms] if slotted and s0 <= 1e-6 else []
        for side, a_, b_, asm_t, page in (("L", 0.0, half - 0.5, asm_tab_l, host.p1),
                                          ("R", half + 0.5, w, asm_tab_r, host.p2)):
            parts = [(a_, b_)]
            for g0, g1 in gaps:
                parts = [q for p0, p1 in parts
                         for q in ((p0, min(p1, g0)), (max(p0, g1), p1)) if q[1] - q[0] > 1.0]
            for j, (p0, p1) in enumerate(parts):
                c_ = min(ch, 0.3 * (p1 - p0))
                self.add(Panel(f"{base}.Tab{side}{j + 1 if j else ''}", piece, "tab",
                               [[(-tb, p0 + c_), (0, p0), (0, p1), (-tb, p1 - c_)]],
                               asm_t, page, None,
                               f"{lab}: tab {'left' if side == 'L' else 'right'}"
                               f"{f' {j + 1}' if j else ''}"))
        self.line_frames[uid] = (piece, lambda q: (q[0], q[1]), (0.0, h, 0.0, w))
        if slotted:
            for k, y_ in enumerate(yms):
                self._riser_cross(m, host, sheet, base, g, hc, y0 + y_, sw,
                                  (mid, hc) if h >= hc else (0.0, mid), k)
            return
        room = min(h, 0.5 * w - 1.0, self.W if host.is_spine else g)
        if g > room + 1e-6:
            g = max(2.0, room)
            self.warn(f"{lab}: 45° folds made {g:.0f} mm to fit the sheet")
        tbb = min(tb, 0.5 * g)
        Ty = Matrix.Translation((0.0, -y0, 0.0))
        flip = Ty @ Matrix.Rotation(math.pi, 4, "Y")  # the sheet's other face
        corners = (
            (Host(self, host.p1, 0.0, 0.0, sheet.name, 0.0, 0.0, f"{lab}: left face",
                  host.T1, Ty), y0 + 0.5, 1.0, "left"),
            (Host(self, sheet.name, 0.0, 0.0, host.p2, 0.0, 0.0, f"{lab}: right face",
                  flip, host.T2), y0 + w - 0.5, -1.0, "right"))
        for k, (hf, yb, lean, txt) in enumerate(corners):
            hf.finish()
            hf.trig = False
            n0 = len(self.order)
            self._brace(uid, k, hf, yb, g, lean, tbb, f"{lab}: 45° fold {txt}")
            for name in self.order[n0:]:
                hg = self.panels[name].hinge
                if hg is not None and hg.kind in ("LINEAR", "SPHERICAL", "EXPR"):
                    hg.kind = "TABLE"

    def _riser_cross(self, m, host, sheet, base, g, hc, yc, sw, slot, k=0):
        """The slotted piece across a rising sheet (Birmingham 81): its
        middle stands in the sheet's slot, square to the fold when the card
        is flat and turning flat against the sheet as it shuts; a 45 degree
        triangle each side of its foot folds down onto a page, where a tab
        glues it (left: up the card from it; right: down)."""
        uid, lab = m["uid"], m["label"]
        tb = min(float(m.get("tab", 10.0)), 0.6 * g)
        cw = max(2.0 * g, float(m.get("cross_width", 0.0) or 0.0))
        piece = f"{base}x{k + 1 if k else ''}"
        self.add_piece(Piece(piece, f"{lab} cross piece{f' {k + 1}' if k else ''}",
                             500 + 4 * uid + k, (0.5 * hc, 0.0)))
        lift1, lift2 = host.lift
        r2 = math.sqrt(2.0)

        def geo(t):
            S, l, r, Y, nl, nr = host.dirs(t)
            b = self._bisector(host, t)
            c = max(0.0, min(1.0, l.dot(b)))  # cos of the corner each side
            a_ = math.sqrt(0.5) / (1.0 + c)
            s_ = math.sqrt(max(0.0, c / (1.0 + c)))
            cL = a_ * (l + b) + s_ * Y
            cR = a_ * (r + b) - s_ * Y
            d = cR - cR.dot(b) * b
            if d.length < 1e-9:
                d = r - r.dot(b) * b
            return S + yc * Y, l, r, Y, nl, nr, b, cL.normalized(), cR.normalized(), d.normalized()

        def asm_x(t):
            P, l, r, Y, nl, nr, b, cL, cR, d = geo(t)
            return frame(P, b, d)

        def asm_l(t):
            P, l, r, Y, nl, nr, b, cL, cR, d = geo(t)
            return frame(P, r2 * cL - l, -l)

        def asm_r(t):
            P, l, r, Y, nl, nr, b, cL, cR, d = geo(t)
            return frame(P, r2 * cR - r, r)

        def asm_tl(t):
            P, l, r, Y, nl, nr, b, cL, cR, d = geo(t)
            return frame(P + lift1 * TAB_LIFT * nl, -Y, -l)

        def asm_tr(t):
            P, l, r, Y, nl, nr, b, cL, cR, d = geo(t)
            return frame(P + lift2 * TAB_LIFT * nr, Y, r)

        a0, a1 = slot  # the cross piece's own slot, up its middle line
        polys = []
        for sg in (-1.0, 1.0):
            polys.append([(0.0, sg * sw), (g, sg * sw), (g, sg * g)])  # 45 degree triangle
            polys.append([(g, sg * sw), (hc, sg * sw), (hc, sg * 0.5 * cw), (g, sg * 0.5 * cw)])
        for x0, x1 in ((0.0, a0), (a1, hc)):
            if x1 - x0 > 1e-6:
                polys.append([(x0, -sw), (x1, -sw), (x1, sw), (x0, sw)])
        slot_line = hinge_frame_2d((0.0, 0.0), (1.0, 0.0))
        cross = self.add(Panel(f"{piece}.Cross", piece, "panel", polys, asm_x, sheet.name,
                               Hinge(hinge_frame_2d((0.0, yc - float(m["y"])), (1.0, 0.0)),
                                     slot_line, "TABLE"), f"{lab}: cross piece"))
        cross.hinge.kink_ok = True
        self.fold_kind[frozenset((sheet.name, cross.name))] = "cut"  # (slots, not a fold)
        ch = 0.3 * tb
        for side, sg, asm_f, asm_t, page in (("L", -1.0, asm_l, asm_tl, host.p1),
                                             ("R", 1.0, asm_r, asm_tr, host.p2)):
            crease = hinge_frame_2d((0.0, 0.0), (1.0, sg))
            self.add(Panel(f"{piece}.Foot{side}", piece, "panel",
                           [[(0.0, sg * sw), (g, sg * g), (0.0, sg * g)]], asm_f, cross.name,
                           Hinge(crease, crease, "TABLE"),
                           f"{lab}: 45° fold {'left' if side == 'L' else 'right'}"))
            self.add(Panel(f"{piece}.Tab{side}", piece, "tab",
                           [[(0.0, sg * sw), (0.0, sg * g), (-tb, sg * (g - ch)),
                             (-tb, sg * (sw + ch))]], asm_t, page, None,
                           f"{lab}: 45° fold tab {'left' if side == 'L' else 'right'}"))

    def _tri45(self, m, hc, which, y0, w, a, b, k, base, lab):
        """Birmingham 74: a pair of small triangles cut into the corner of a
        box fold (where its top meets its front) at its top or bottom edge,
        on a 45 degree fold: they swing up out of the box as the card
        closes, carrying the pictures stuck on them."""
        h = float(m.get("tri_size", 12.0) or 12.0)
        if abs(k) > 1e-9:
            self.warn(f"{lab}: 45° triangles need a box that isn't slanted; left out")
            return
        if h > min(a, b) - 0.5 or 2.0 * h > w + 1e-6:
            h = max(2.0, min(min(a, b) - 0.5, 0.5 * w))
            self.warn(f"{lab}: 45° triangles made {h:.0f} mm to fit the box")
        piece = self.panels[hc.p1].piece
        v, d = hc.v1, hc.d1
        s2 = math.sqrt(0.5)
        q45 = math.radians(45.0)
        ends = []
        if which in ("TOP", "BOTH"):
            ends.append(("T", y0 + w - h, 1.0, "top"))
        if which in ("BOTTOM", "BOTH"):
            ends.append(("B", y0 + h, -1.0, "bottom"))
        for tag, yp, sy, txt in ends:
            ye = yp + sy * h
            cells = {}
            for side, sx, pn in (("L", -1.0, hc.p1), ("R", 1.0, hc.p2)):
                got = self.carve(piece, [v(0.0, yp), v(sx * h, ye), v(0.0, ye)], {pn}, lab)
                if got is None:
                    return
                cells[side] = got
            key = f"{base}.Tri{tag}"
            self.joints[key] = dict(host=hc, y=yp, uL=(-s2, sy * s2), uR=(s2, sy * s2),
                                    aL=q45, aR=q45, rise=True)
            P = v(0.0, yp)
            for side, sx in (("L", -1.0), ("R", 1.0)):
                self._half(f"{key}{side}", piece, cells[side], P, d(sx * s2, sy * s2),
                           d(0.0, sy), side, key, f"{lab}: {txt} triangle "
                           f"{'left' if side == 'L' else 'right'}")
            self.match_lift(f"{key}L", f"{key}R")
            self.cut_panels |= {f"{key}L", f"{key}R"}
            if any(not self.crease(key, s_)[3] for s_ in self.samples):
                self.warn(f"{lab}: its 45° triangles tear on this host")

    # ------------------------------------------------------- jack in the box
    def _jack(self, m, host, cut_in):
        """Birmingham 79: a figure on two pairs of 45 degree folds cut into
        the top of any V-fold's crease (the V-fold its body; 78's strap body
        isn't built: its arms would go through the pages). On the crease a
        45 degree fold leans the chest back into the V as the card closes,
        its arms (out past the chest's sides) swinging round in front; on
        the chest's crease a second one lifts the head. G (Height) is the same between all the parallel
        lines: from the centre to each side, between the two folds' points
        (F - G and F) and from F up to the arms' top edge (E)."""
        uid, lab = m["uid"], m["label"]
        G, R = float(m["height"]), float(m.get("depth", 30.0))
        hh = 0.7 * G  # the head above E
        s2 = math.sqrt(0.5)
        q45 = math.radians(45.0)
        if cut_in:  # on a V-fold's crease: F up the crease from its point
            if not host.cut_ok or host.key is None or host.key[1] != "V":
                self.warn(f"{lab}: goes on a V-fold's crease; skipped")
                return
            F = float(m["y"])
            body = host
        else:
            # 78 (on a strap) needs arms that bend: they reach past the strips
            # it is glued down by, where stiff paper would go through the page
            self.warn(f"{lab}: stands on a V-fold's crease (Birmingham 79); skipped")
            return
        E = F + G
        if host.is_spine and E + hh > self.H + 1e-6:
            self.warn(f"{lab}: the head runs past the top of the card")
        piece = self.panels[body.p1].piece
        v = body.v1

        def on_paper(pn, q):
            return any(all(n[0] * q[0] + n[1] * q[1] >= d - 1e-6 for n, d in halfplanes(poly))
                       for poly in self.panels[pn].polys)

        # the chest's folds must lie on the V-fold's halves, or it hangs free
        for pn, sg in ((body.p1, -1.0), (body.p2, 1.0)):
            if not all(on_paper(pn, v(sg * G * f, F - G + G * f))
                       for f in (0.02, 0.25, 0.5, 0.75, 0.98)):
                self.warn(f"{lab}: its chest's folds run off the V-fold (lower it down the "
                          f"crease, or make Fold Spacing smaller); skipped")
                return
        # the figure is cut free of the body: above the lower V and line F
        big = E + hh + 1.0
        for side, sg in ((("L", -1.0), ("R", 1.0)) if cut_in else ()):
            pn = body.p1 if side == "L" else body.p2
            for reg in ([(0, F - G), (sg * G, F), (sg * G, big), (0, big)],
                        [(sg * G, F), (sg * (G + R + 1.0), F), (sg * (G + R + 1.0), big),
                         (sg * G, big)]):
                hps = halfplanes(ccw([v(*q) for q in reg]))
                p = self.panels[pn]
                outs = []
                for poly in p.polys:
                    outs += split_convex(poly, hps)[0]
                p.polys = [ccw(q) for q in outs]
        names = {}
        k1, k2 = f"Jack{uid}.C", f"Jack{uid}.H"
        self.joints[k1] = dict(host=body, y=F - G, uL=(-s2, s2), uR=(s2, s2), aL=q45, aR=q45,
                               rise=True)
        d = body.d1
        n0 = len(self.order)
        for side, sg in (("L", -1.0), ("R", 1.0)):
            chest = [[v(0, F - G), v(sg * G, F), v(sg * G, E), v(0, F)],
                     [v(sg * G, F), v(sg * (G + R), F), v(sg * (G + R), E), v(sg * G, E)]]
            g = (sg * s2, s2)
            names[side] = self._half(f"Jack{uid}.Chest{side}", piece, chest, v(0, F - G),
                                     d(*g), d(0, 1), side, k1,
                                     f"{lab}: chest and {'left' if side == 'L' else 'right'} "
                                     f"arm").name
        self.match_lift(names["L"], names["R"])
        T = body.T1
        h2 = Host(self, names["L"], 0.0, 0.0, names["R"], 0.0, 0.0, f"{lab}: chest", T,
                  body.T2).finish()
        h2.trig = False
        self.joints[k2] = dict(host=h2, y=F, uL=(-s2, s2), uR=(s2, s2), aL=q45, aR=q45,
                               rise=True)
        hw = 0.6 * G
        for side, sg in (("L", -1.0), ("R", 1.0)):
            head = [[v(0, F), v(sg * G, E), v(0, E)],
                    [v(sg * hw, E), v(0, E), v(0, E + hh), v(sg * 0.6 * hw, E + hh)]]
            g = (sg * s2, s2)
            self._half(f"Jack{uid}.Head{side}", piece, head, v(0, F), d(*g), d(0, 1), side,
                       k2, f"{lab}: head {'left' if side == 'L' else 'right'}")
        self.match_lift(f"Jack{uid}.HeadL", f"Jack{uid}.HeadR")
        for name in self.order[n0:]:
            hg = self.panels[name].hinge
            if hg is not None and hg.kind in ("LINEAR", "SPHERICAL", "EXPR"):
                hg.kind = "TABLE"  # on folds that don't open evenly with the card
        self.cut_panels |= {n for n in self.order[n0:]}
        for k in (k1, k2):
            if any(not self.crease(k, s)[3] for s in self.samples):
                self.warn(f"{lab}: its 45° folds tear on this host")
                break

    # ------------------------------------------------------- double 45 fold
    def _double45(self, m, host):
        """Birmingham 77, the double 45 degree fold. An arms piece glued to
        both pages by the two triangles either side of its centre point C
        (D and E), with four 45 degree valley folds from C to its edges:
        above C and below C a 45 degree fold each, so both arms rise as the
        card closes, one leaning up the card and one down it. A top piece
        joins the arm tips, glued on diagonally (the upper right half's tip
        and the lower left half's): as the arms rise it twists round.

        The arms are exact. The top piece can't be exact with stiff paper
        (its two hinge lines aren't parallel as it turns), so on screen each
        half is stiff out to a narrow band either side of its centre fold G,
        and the band bends and twists between them; it prints as the one
        piece Birmingham draws."""
        uid, lab = m["uid"], m["label"]
        w, La = float(m["width"]), float(m["height"])
        Lt = 0.5 * float(m["depth"])
        y0, tb = float(m["y"]), float(m.get("tab", 10.0))
        hw = 0.5 * w
        if La < hw + 2.0:
            self.warn(f"{lab}: arms must be longer than half their width (the 45° folds "
                      f"reach the edges at {hw:.0f} mm)")
            return
        if Lt <= La + 0.5:
            self.warn(f"{lab}: the top piece must be longer than the arms "
                      f"(more than {2 * La:.0f} mm), or it can't arch over them")
            return
        if y0 - La - tb < -1e-6 or y0 + La + tb > self.H + 1e-6:
            self.warn(f"{lab}: runs past the top or bottom of the card")
        base = f"D45{uid}"
        piece, tpiece = base, f"{base}T"
        self.add_piece(Piece(piece, lab, 1 + uid, (0.0, 0.0)))
        self.add_piece(Piece(tpiece, f"{lab} top", 700 + uid, (0.0, 0.0)))
        r = min(3.0, 0.15 * w)  # the hole round C (fewer layers there when shut)
        q45 = math.radians(45.0)
        s2 = math.sqrt(0.5)

        def cut(poly, *dirs):
            n = unit2(sum(d[0] for d in dirs), sum(d[1] for d in dirs))
            return clip_halfplane(poly, n, r)

        U, D = f"{base}.U", f"{base}.D"
        self.joints[U] = dict(host=host, y=y0, uL=(-s2, s2), uR=(s2, s2), aL=q45, aR=q45)
        self.joints[D] = dict(host=host, y=y0, uL=(-s2, -s2), uR=(s2, -s2), aL=q45, aR=q45)
        halves = (
            ("UL", U, "L", [(0, 0), (0, La), (-hw, La), (-hw, hw)], (-s2, s2), (0, 1),
             "upper arm left"),
            ("UR", U, "R", [(0, 0), (hw, hw), (hw, La), (0, La)], (s2, s2), (0, 1),
             "upper arm right"),
            ("LL", D, "L", [(0, 0), (-hw, -hw), (-hw, -La), (0, -La)], (-s2, -s2), (0, -1),
             "lower arm left"),
            ("LR", D, "R", [(0, 0), (0, -La), (hw, -La), (hw, -hw)], (s2, -s2), (0, -1),
             "lower arm right"))
        for nm, key, side, poly, g, c, txt in halves:
            self._half(f"{base}.{nm}", piece, [cut(poly, g, c)], (0, 0), g, c, side, key,
                       f"{lab}: {txt}")
        self.match_lift(f"{base}.UL", f"{base}.UR")
        self.match_lift(f"{base}.LL", f"{base}.LR")
        # D and E: glued flat, the piece's own way up
        lift1, lift2 = host.lift
        for nm, poly, n, parent, V, lift in (
                ("D", [(0, 0), (-hw, -hw), (-hw, hw)], (-1, 0), host.p1, host.T1, lift1),
                ("E", [(0, 0), (hw, hw), (hw, -hw)], (1, 0), host.p2, host.T2, lift2)):
            pa = self.panels[parent].asm
            T = V @ Matrix.Translation((0.0, y0, lift * TAB_LIFT))
            self.add(Panel(f"{base}.Glue{nm}", piece, "tab", [clip_halfplane(poly, n, r)],
                           (lambda t, pa=pa, T=T: pa(t) @ T), parent, None,
                           f"{lab}: glue {nm}"))
        if any(not self.crease(k, s)[3] for k in (U, D) for s in self.samples):
            self.warn(f"{lab}: its 45° folds tear on this host")

        # ---- the top piece: F (y = Lt) on the upper right tip, H (y = -Lt)
        # on the lower left one, G (y = 0) its centre fold. The whole piece is
        # symmetric about the turn axis through C halfway between the pages
        # (half a turn about it swaps the halves), so G lies on that axis, a
        # half's length from each tip. Each half is shown as a strip twisting
        # from its tip's edge to G: its rows blend from where the half's hinge
        # on the tip puts them to where a frame at G does.
        UR, LL = self.panels[f"{base}.UR"], self.panels[f"{base}.LL"]
        Hu, Fu = hinge_frame_2d((0.0, La), (1, 0)), hinge_frame_2d((0.0, Lt), (1, 0))
        Hd, Fd = hinge_frame_2d((0.0, -La), (-1, 0)), hinge_frame_2d((0.0, -Lt), (-1, 0))
        Fui, Fdi = Fu.inverted(), Fd.inverted()
        O = Vector((0.0, 0.0, 0.0))
        cache = {}

        def geo(t):
            """(G, its fold's direction, the way to F from it, the turn about
            the axis) at opening t."""
            got = cache.get(t)
            if got is None:
                S, l, rr, Y, nl, nr = host.dirs(t)
                C = S + y0 * Y
                b = self._bisector(host, t)
                A = UR.asm(t)
                tip = A @ Vector((0.0, La, 0.0))
                e1 = (A.to_3x3() @ Vector((1.0, 0.0, 0.0))).normalized()
                d = tip - C
                db = d.dot(b)
                G = C + b * (db + math.sqrt(max(db * db - d.length_squared + Lt * Lt, 0.0)))
                # G's fold: square to the axis (half a turn about it maps it
                # onto itself), turned so the half's two edges stay as long as
                # each other (pure twist, no shear): (tip - G) . dG = (tip - G) . e1
                a = tip - G
                ap = a - b * a.dot(b)
                k = a.dot(e1)
                if ap.length < 1e-9:
                    dG = (e1 - b * e1.dot(b)).normalized()
                else:
                    ah = ap.normalized()
                    side = b.cross(ah)
                    # where no turn keeps them equal (near shut) a hard limit
                    # would pinch the fold at G shut, the halves crossing: ease
                    # off instead, keeping G open
                    # (shut, there's no room between the pages for it open:
                    # the limit eases back to the pinch as the host closes)
                    op = math.degrees(l.angle(rr))
                    ramp = max(0.0, min(1.0, op / 60.0))
                    cap = math.cos(math.radians(40.0 * ramp * ramp * (3 - 2 * ramp)))
                    r_ = k / ap.length
                    al = r_ / (1.0 + abs(r_ / cap) ** 6) ** (1.0 / 6.0)
                    be = math.sqrt(1.0 - al * al)
                    dG = ah * al + side * (be if e1.dot(side) >= 0 else -be)
                nB = tip - G
                nB = (nB - dG * nB.dot(dG)).normalized()
                Rb = (Matrix.Translation(C) @ Matrix.Rotation(math.pi, 4, b) @
                      Matrix.Translation(-C))
                got = cache[t] = (G, dG, nB, Rb, tip)
                if len(cache) > 4096:
                    cache.clear()
            return got

        def gap(t, psi):
            return (UR.asm(t) @ Hu @ rot_y(psi) @ Fui @ O - geo(t)[0]).length

        def best(t, lo, hi, n=24):
            for _ in range(5):
                xs = [lo + (hi - lo) * k / n for k in range(n + 1)]
                k = min(range(n + 1), key=lambda k: gap(t, xs[k]))
                step = (hi - lo) / n
                lo, hi = xs[k] - step, xs[k] + step
            return 0.5 * (lo + hi)

        Ts = sorted(self.TABLE_T, reverse=True)
        # fully open: arched over the arms, printed side out
        psi = best(Ts[0], -math.pi + 1e-3, -1e-3, 180)
        table = {}
        for t in Ts:
            psi = best(t, psi - 0.15, psi + 0.15, 12)
            table[t] = psi
        Tk = sorted(table)

        def psi_at(t):
            t = min(max(t, Tk[0]), Tk[-1])
            i = max(0, min(len(Tk) - 2, bisect.bisect_right(Tk, t) - 1))
            t0_, t1_ = Tk[i], Tk[i + 1]
            f = (t - t0_) / (t1_ - t0_)
            return table[t0_] + f * (table[t1_] - table[t0_])

        def asm_up(t):
            return UR.asm(t) @ Hu @ rot_y(psi_at(t)) @ Fui

        def asm_dn(t):
            return LL.asm(t) @ Hd @ rot_y(psi_at(t)) @ Fdi

        def asm_gf(t):
            G, dG, nB, Rb, tip = geo(t)
            return frame(G, dG, nB)

        flipz = Matrix.Rotation(math.pi, 4, "Z")

        def asm_gh(t):
            return geo(t)[3] @ asm_gf(t) @ flipz

        rows = 8

        def strip(y_a, y_b):
            return [[(-hw, y_a + (y_b - y_a) * k / rows), (hw, y_a + (y_b - y_a) * k / rows),
                     (hw, y_a + (y_b - y_a) * (k + 1) / rows),
                     (-hw, y_a + (y_b - y_a) * (k + 1) / rows)] for k in range(rows)]

        h2 = 0.5 * Lt
        up = self.add(Panel(f"{base}.TopF", tpiece, "panel", strip(h2, Lt), asm_up, UR.name,
                            Hinge(Hu, Fu, "TABLE"), f"{lab}: top piece, F half"))
        dn = self.add(Panel(f"{base}.TopH", tpiece, "panel", strip(-Lt, -h2), asm_dn,
                            LL.name, Hinge(Hd, Fd, "TABLE"), f"{lab}: top piece, H half"))
        gf = self.add(Panel(f"{base}.GF", tpiece, "panel", strip(0.0, h2), asm_gf, up.name,
                            None, f"{lab}: top piece, F half at G"))
        gh = self.add(Panel(f"{base}.GH", tpiece, "panel", strip(-h2, 0.0), asm_gh, dn.name,
                            None, f"{lab}: top piece, H half at G"))
        gf.free = gh.free = True  # not fixed to anything: posed opening by opening
        # stiff with its hinge as far as the tab glued under it reaches
        ya = Lt - min(tb, 0.3 * Lt)
        for p_, a_, b_, ya in ((up, up, gf, ya), (gf, up, gf, ya), (dn, dn, gh, -ya),
                               (gh, dn, gh, -ya)):
            self.blend[p_.name] = (a_.name, b_.name, ya, 0.0)
        # on paper: one piece, its only fold G
        self.fold_kind[frozenset((up.name, gf.name))] = "skip"
        self.fold_kind[frozenset((dn.name, gh.name))] = "skip"
        self.fold_kind[frozenset((gf.name, gh.name))] = "mountain"
        # how far a half has to twist (between its tip's edge and G)
        worst = max(math.degrees(math.acos(max(-1.0, min(1.0, geo(t)[1].dot(
            (UR.asm(t).to_3x3() @ Vector((1.0, 0.0, 0.0))).normalized()))))) for t in Tk)
        # tabs I (upper right tip) and K (lower left), folded back under the
        # top piece's ends and glued there: J and L
        ch = min(0.3 * tb, 0.2 * hw)
        flipx = Matrix.Rotation(math.pi, 4, "X")
        for nm, poly, parent, pasm, M in (
                ("I", [(0.5, La), (hw, La), (hw - ch, La + tb), (0.5 + ch, La + tb)], up,
                 asm_up, Matrix.Translation((0.0, La + Lt, -TAB_LIFT)) @ flipx),
                ("K", [(-hw, -La), (-0.5, -La), (-0.5 - ch, -La - tb), (-hw + ch, -La - tb)],
                 dn, asm_dn, Matrix.Translation((0.0, -La - Lt, -TAB_LIFT)) @ flipx)):
            self.add(Panel(f"{base}.Tab{nm}", piece, "tab", [poly],
                           (lambda t, pasm=pasm, M=M: pasm(t) @ M), parent.name, None,
                           f"{lab}: tab {nm}"))
        self.line_frames[uid] = (piece, lambda q: q, None)
        self.d45_twist = getattr(self, "d45_twist", {})
        self.d45_twist[uid] = worst
        if host.is_spine:
            reach = 0.0
            for nm in (f"{base}.TopF", f"{base}.TopH"):
                p = self.panels[nm]
                for t in (T_MIN, 10.0, 30.0):
                    S, l, rr, Y, nl, nr = host.dirs(t)
                    b = self._bisector(host, t)
                    for q in p.polys[0]:
                        reach = max(reach, (p.asm(t) @ v3(q) - S).dot(b))
            if reach > self.W + 1e-6:
                self.warn(f"{lab}: reaches {reach:.0f} mm from the fold when shut, past "
                          f"the page ({self.W:.0f} mm)")
