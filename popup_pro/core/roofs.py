"""Roofs on parallel strips and tubes (Birmingham 52, 67): pyramids, tents,
ridge roofs, flat roofs and the centre rib."""
import math

from mathutils import Matrix, Vector

from .base import halfplanes, Host, Panel, Piece, poly_area, TAB_LIFT
from .geom import ccw, clip_halfplane, frame, v3


class Roofs:
    """Roof builders. Mixed into Model (model.py)."""

    def _flat_roof(self, uid, lab, host, a, y0, D, wf, wb, sf, sb, hgt, eave, fold, tb,
                   wl, wr, u3, rib=0.0, tube=None):
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
        T_ = self.tubes.get(tube) if tube is not None else None
        if T_ is not None and (T_.get("rf") or T_.get("rb")):
            # a round front or back: the roof follows the walls' curve when open
            pl = self.tube_plan(tube, self.tmax)
            back = ["CB"] + [f"bL{k}" for k in range(T_["nb"] - 1, 0, -1)] if T_["rb"] \
                else ["CB"]
            front = [f"fL{k}" for k in range(1, T_["nf"])] + ["CF"] if T_["rf"] else ["CF"]
            outline = [(0.0, pl["CB"][1]) if k == "CB" else pl[k] for k in back] + \
                [(-a, y0 + D), (-a, y0)] + \
                [(0.0, pl["CF"][1]) if k == "CF" else pl[k] for k in front]

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
        lines = [line(outline[i], outline[i + 1], -e_) for i in range(len(outline) - 1)]
        mid = ((0.0, 0.0), (0.0, 1.0))
        polyL = [meet(mid, lines[0])] + [meet(lines[i], lines[i + 1])
                                         for i in range(len(lines) - 1)] + \
            [meet(lines[-1], mid)]
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
            self.add(Panel(f"Tube{uid}.Top{side}", wall.piece, "tab", [poly],
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
        self.add(Panel(f"{piece}.W2", piece, "panel", [[(y2, 0), (y2 + L, 0),
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
        a, y0 = float(m["x"]), float(m["y"])
        D = float(m["depth"])
        wf, wb = max(float(m["front"]), a), max(float(m["back"]), a)
        if float(m["front"]) < a - 1e-6 or float(m["back"]) < a - 1e-6:
            self.warn(f"{lab}: front and back must be at least as wide as the strip "
                      f"distance; widened to {a:.0f} mm")
        if "ROUND" in (m.get("front_style"), m.get("back_style")):
            self.warn(f"{lab}: a pyramid can't have a round front or back; pointed out "
                      f"instead")
        sf = 1.0 if m.get("front_style", "OUT") in ("OUT", "ROUND") else -1.0
        sb = 1.0 if m.get("back_style", "OUT") in ("OUT", "ROUND") else -1.0
        tb = min(float(m.get("tab", 10.0)), 0.45 * D)
        self._roof(uid, f"Pyramid{uid}", lab, 1 + uid, host, a, y0, D, wf, wb, sf, sb, 0.0,
                   float(m["height"]), float(m.get("ridge", 0.0)), tb,
                   m.get("tab_side", "IN"))

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
