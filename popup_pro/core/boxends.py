"""Box ends (Birmingham 82): a box on one page, one side along the fold,
pulled up by a 45 degree fold from the other page, its ends filled in by two
more.

model.py has the module's overview and the Model class."""
import math

from mathutils import Matrix, Vector

from .base import Hinge, Host, Panel, Piece, TAB_LIFT
from .geom import frame, hinge_frame_2d


class BoxEnds:
    """Box-ends builder. Mixed into Model (model.py)."""

    def _boxend(self, m, host):
        """A box (a parallelogram: wall, top, wall) glued to one page only,
        its first wall rising from the fold itself. Both feet are on the
        same page, so the card's opening doesn't move it: a 45 degree fold
        from the other page to that wall pulls it up. The fold lets the wall
        come no further than square to its page, so the box lies flat on its
        own page until the card is half open and stands square when it is
        flat. Each end is filled by two 45 degree folds in the two corners
        that close as the box flattens (wall and page; top and far wall),
        cut along the end's diagonal: one face of each is part of the box,
        the other glued by a tab."""
        uid, lab = m["uid"], m["label"]
        w, d, hh = float(m["width"]), float(m["depth"]), float(m["height"])
        y0 = float(m["y"])
        tb = float(m.get("tab", 10.0))
        ends = m.get("box_ends", "BOTH")
        if m.get("box_side", "R") == "L":
            # the same thing turned half round: built as if on the right
            R = Matrix.Rotation(math.pi, 4, "Z")
            host = Host(self, host.p2, 0.0, 0.0, host.p1, 0.0, 0.0, host.label,
                        host.T2 @ R, host.T1 @ R).finish()
            host.trig = False
            y0 = -(y0 + w)
            ends = {"FRONT": "BACK", "BACK": "FRONT"}.get(ends, ends)
        if host.is_spine:
            if y0 < -1e-6 or y0 + w > self.H + 1e-6:
                self.warn(f"{lab}: runs past the top or bottom of the card")
            if d + hh > self.W + 1e-6:
                self.warn(f"{lab}: lying flat it reaches {d + hh:.0f} mm from the fold, past "
                          f"the page's edge ({self.W:.0f} mm)")
        piece = f"BoxE{uid}"
        self.add_piece(Piece(piece, lab, 1 + uid, (hh + 0.5 * d, 0.5 * w)))
        up_s = host.lift[1]
        xB, xI = hh + d, 2.0 * hh + d  # strip: tab | wall A | top | wall B | tab
        r2 = math.sqrt(2.0)

        def geo(t):
            S, l, r, Y, nl, nr = host.dirs(t)
            up = up_s * nr
            gam = math.acos(max(-1.0, min(1.0, l.dot(r))))
            th = max(0.0, gam - 0.5 * math.pi)  # the wall's angle off its page
            u = math.cos(th) * r + math.sin(th) * up
            return S + y0 * Y, r, u, Y, up, th

        def crease(g1, g2, n):
            """A 45 degree fold's crease, between glue lines g1 and g2 out
            of one point, popping towards n."""
            c = max(0.0, min(1.0, g1.dot(g2)))
            return (math.sqrt(0.5) / (1.0 + c) * (g1 + g2) +
                    math.sqrt(max(0.0, c / (1.0 + c))) * n).normalized()

        def asm_a(t):
            F, r, u, Y, up, th = geo(t)
            return frame(F, u, Y)

        def asm_top(t):
            F, r, u, Y, up, th = geo(t)
            return frame(F + hh * u, r, Y) @ Matrix.Translation((-hh, 0.0, 0.0))

        def asm_b(t):
            F, r, u, Y, up, th = geo(t)
            return frame(F + d * r + hh * u, -u, Y) @ Matrix.Translation((-xB, 0.0, 0.0))

        def asm_g(t):
            F, r, u, Y, up, th = geo(t)
            return frame(F + TAB_LIFT * up, -r, Y)

        tab_in = m.get("far_tab", "OUT") == "IN"

        def asm_i(t):
            F, r, u, Y, up, th = geo(t)
            # out from the box along the page, or (In) folded back under it
            return frame(F + d * r + TAB_LIFT * up, -r if tab_in else r, Y) @ \
                Matrix.Translation((-xI, 0.0, 0.0))

        fy = hinge_frame_2d((0.0, 0.0), (0.0, 1.0))
        wall = self.add(Panel(f"{piece}.A", piece, "panel",
                              [[(0, 0), (hh, 0), (hh, w), (0, w)]], asm_a, host.p2,
                              Hinge(host.T2 @ hinge_frame_2d((0.0, y0), (0, 1)), fy, "TABLE"),
                              f"{lab}: wall on the fold"))
        if wall is None:
            return
        f1 = hinge_frame_2d((hh, 0.0), (0.0, 1.0))
        top = self.add(Panel(f"{piece}.Top", piece, "panel",
                             [[(hh, 0), (xB, 0), (xB, w), (hh, w)]], asm_top, wall.name,
                             Hinge(f1, f1, "TABLE"), f"{lab}: top"))
        f2 = hinge_frame_2d((xB, 0.0), (0.0, 1.0))
        far = self.add(Panel(f"{piece}.B", piece, "panel",
                             [[(xB, 0), (xI, 0), (xI, w), (xB, w)]], asm_b, top.name,
                             Hinge(f2, f2, "TABLE"), f"{lab}: far wall"))
        for p in (wall, top, far):
            p.hinge.kink_ok = True  # (it starts to rise when the card is half open)
        ch = min(0.3 * tb, 0.1 * w)
        self.add(Panel(f"{piece}.TabG", piece, "tab",
                       [[(-tb, ch), (0, 0), (0, w), (-tb, w - ch)]], asm_g, host.p2, None,
                       f"{lab}: tab on the fold"))
        self.add(Panel(f"{piece}.TabI", piece, "tab",
                       [[(xI, 0), (xI + tb, ch), (xI + tb, w - ch), (xI, w)]], asm_i, host.p2,
                       None, f"{lab}: far tab"))
        self.line_frames[uid] = (piece, lambda q_: (q_[0], q_[1]), (0.0, xI, 0.0, w))
        if tab_in and 2.0 * tb > d + 1e-6:
            self.warn(f"{lab}: its two foot tabs overlap under the box ({d:.0f} mm wide); "
                      f"use smaller tabs or put the far tab outside")

        # ---- the ends
        q = d * hh / (d + hh)  # where a 45 degree crease meets the end's diagonal
        te = max(2.0, min(tb, 0.5 * d, 0.5 * hh))
        for end, e, ye in (("F", -1.0, 0.0), ("K", 1.0, w)):
            if ends not in ("BOTH", "FRONT" if end == "F" else "BACK"):
                continue
            txt = "front end" if end == "F" else "back end"
            Tp = Matrix.Translation((0.0, -ye, 0.0))

            def parts(t, e=e, ye=ye):
                F, r, u, Y, up, th = geo(t)
                n = -e * Y  # into the box
                P = F + ye * Y
                P2 = P + d * r + hh * u
                return P, P2, r, u, n, up, crease(r, u, n), crease(-r, -u, n)

            # corner of the page and the wall on the fold
            def asm_wa(t, e=e, parts=parts, Tp=Tp):
                P, P2, r, u, n, up, c1, c2 = parts(t)
                return frame(P, u, e * (r2 * c1 - u)) @ Tp

            def asm_pg(t, e=e, parts=parts, Tp=Tp):
                P, P2, r, u, n, up, c1, c2 = parts(t)
                return frame(P, r2 * c1 - r, e * r) @ Tp

            def asm_h(t, e=e, parts=parts, Tp=Tp):
                P, P2, r, u, n, up, c1, c2 = parts(t)
                return frame(P + TAB_LIFT * up, -n, e * r) @ Tp

            # corner of the top and the far wall
            def asm_tp(t, e=e, parts=parts, Tp=Tp):
                P, P2, r, u, n, up, c1, c2 = parts(t)
                return frame(P2, r, e * (r2 * c2 + r)) @ Matrix.Translation((-xB, 0.0, 0.0)) @ Tp

            def asm_fw(t, e=e, parts=parts, Tp=Tp):
                P, P2, r, u, n, up, c1, c2 = parts(t)
                return frame(P2, -(r2 * c2 + u), -e * u) @ \
                    Matrix.Translation((-xB, 0.0, 0.0)) @ Tp

            def asm_j(t, e=e, parts=parts, Tp=Tp):
                P, P2, r, u, n, up, c1, c2 = parts(t)
                return frame(P2 - TAB_LIFT * r, n, -e * u) @ \
                    Matrix.Translation((-xB, 0.0, 0.0)) @ Tp

            def Y_(v, e=e, ye=ye):
                return ye + e * v

            edge_a = hinge_frame_2d((0.0, ye), (1.0, 0.0))
            wa = self.add(Panel(f"{piece}.{end}Wa", piece, "panel",
                                [[(0.0, Y_(0)), (q, Y_(q)), (hh, Y_(0))]], asm_wa, wall.name,
                                Hinge(edge_a, edge_a, "TABLE"), f"{lab}: {txt}, on the wall"))
            cr1 = hinge_frame_2d((0.0, ye), (1.0, e))
            pg = self.add(Panel(f"{piece}.{end}Pg", piece, "panel",
                                [[(0.0, Y_(0)), (0.0, Y_(d)), (q, Y_(q))]], asm_pg, wa.name,
                                Hinge(cr1, cr1, "TABLE"), f"{lab}: {txt}, on the page"))
            c_ = 0.3 * te
            self.add(Panel(f"{piece}.{end}TabH", piece, "tab",
                           [[(0.0, Y_(0)), (0.0, Y_(d)), (-te, Y_(d - c_)), (-te, Y_(c_))]],
                           asm_h, host.p2, None, f"{lab}: {txt} tab on the page"))
            edge_t = hinge_frame_2d((xB, ye), (1.0, 0.0))
            tp = self.add(Panel(f"{piece}.{end}Tp", piece, "panel",
                                [[(xB, Y_(0)), (xB - d, Y_(0)), (xB - q, Y_(q))]], asm_tp,
                                top.name, Hinge(edge_t, edge_t, "TABLE"),
                                f"{lab}: {txt}, on the top"))
            cr2 = hinge_frame_2d((xB, ye), (-1.0, e))
            fw = self.add(Panel(f"{piece}.{end}Fw", piece, "panel",
                                [[(xB, Y_(0)), (xB - q, Y_(q)), (xB, Y_(hh))]], asm_fw, tp.name,
                                Hinge(cr2, cr2, "TABLE"), f"{lab}: {txt}, on the far wall"))
            self.add(Panel(f"{piece}.{end}TabJ", piece, "tab",
                           [[(xB, Y_(0)), (xB, Y_(hh)), (xB + te, Y_(hh - c_)),
                             (xB + te, Y_(c_))]], asm_j, far.name, None,
                           f"{lab}: {txt} tab on the far wall"))
            for p in (wa, pg, tp, fw):
                p.hinge.kink_ok = True
            def mid(t):  # (a point inside the box, a little up off its page)
                F, r, u, Y, up, th = geo(t)
                return F + 0.5 * d * r + 0.5 * hh * u + 0.5 * w * Y + up

            if m.get("tucks", True):
                # the book's tuck flaps (C, D): on the diagonal edges of the
                # wall's and the page's triangles, jutting behind the top's
                # and the far wall's, bent a little in so they stay there
                X, W_ = Vector((q, Y_(q))), Vector((hh, Y_(0)))
                F_, Xp = Vector((0.0, Y_(d))), Vector((xB - q, Y_(q)))
                bis = -((W_ - X).normalized() + (F_ - X).normalized())
                for tag, par, P0, P1, tgt, keep in (("C", wa, X, W_, tp, W_),
                                                   ("D", pg, F_, X, fw, F_)):
                    self._tuck(piece, f"{piece}.{end}Tuck{tag}", par, P0, P1, tgt,
                               [(X, X + bis, keep)] + ([(W_, Xp, X)] if tag == "C" else []),
                               mid, f"{lab}: {txt} tuck flap {tag}",
                               min(4.0, 0.3 * q))

        self._boxend_pull(m, host, wall, piece, uid, lab, w, hh, y0, tb)

    def _tuck(self, piece, name, par, P0, P1, tgt, keeps, inside, label, f):
        """A tuck flap off panel par's edge P0-P1 (pattern), f wide, kept
        on each (a, b, side point) line's side that holds the point; it
        lies just behind panel tgt (on the side of it towards inside(t), a
        point inside the box), a few degrees in from it."""
        from .geom import clip_halfplane
        ev = (P1 - P0).normalized()
        cen = Vector([sum(c) / len(c) for c in zip(*[q for poly in par.polys for q in poly])])
        nout = Vector((-ev.y, ev.x))
        if nout.dot(cen - P0) > 0:
            nout = -nout
        sh = 0.12 * (P1 - P0).length  # (clear of the corners)
        poly = [P0 + sh * ev, P1 - sh * ev, P1 - sh * ev + f * nout - 0.5 * f * ev,
                P0 + sh * ev + f * nout + 0.5 * f * ev]
        poly = [tuple(q) for q in poly]
        for a, b, side in keeps:
            n = Vector((-(b - a).y, (b - a).x))
            if n.dot(side - a) < 0:
                n = -n
            poly = clip_halfplane(poly, tuple(n), n.dot(a) + 0.4 * n.length)
            if len(poly) < 3:
                return
        bend = math.radians(10.0)
        Fi = frame(Vector((P0.x, P0.y, 0.0)), Vector((ev.x, ev.y, 0.0)),
                   Vector((nout.x, nout.y, 0.0))).inverted()
        tcen = Vector([sum(c) / len(c) for c in zip(*[q for poly in tgt.polys for q in poly])])
        # (its corners off the hinge: those that can stand behind or in front)
        pts = [q for q in poly if abs(nout.dot(Vector(q) - P0)) > 0.5] or poly

        def asm(t):
            A = par.asm(t)
            a3, b3 = A @ Vector((P0.x, P0.y, 0.0)), A @ Vector((P1.x, P1.y, 0.0))
            ln = (b3 - a3).normalized()
            nt = (tgt.asm(t).to_3x3() @ Vector((0.0, 0.0, 1.0))).normalized()
            mm = nt.cross(ln)
            if mm.length < 1e-9:
                mm = (A.to_3x3() @ Vector((nout.x, nout.y, 0.0)))
            mm = mm.normalized()
            if mm.dot(tgt.asm(t) @ Vector((tcen.x, tcen.y, 0.0)) - a3) < 0:
                mm = -mm  # (towards the panel it tucks behind)
            o = tgt.asm(t) @ Vector((tcen.x, tcen.y, 0.0))
            nin = nt if nt.dot(inside(t) - o) >= 0 else -nt

            def at(al):
                return frame(a3, ln, (math.cos(al) * mm + math.sin(al) * nin).normalized()) @ Fi

            def dists(al):  # (its corners' distances behind the panel: + is behind)
                M_ = at(al)
                return [nin.dot(M_ @ Vector((q[0], q[1], 0.0)) - o) for q in pts]

            # bent in a little, behind the panel. While the end is still
            # opening its hinge can stand out in front of the panel: then it
            # lies in front instead, turned out as far as it must, never
            # through the panel
            hd = max((nin.dot(a3 - o), nin.dot(b3 - o)), key=abs)
            if hd > -0.05:
                def ok(al):
                    return min(dists(al)) >= 0.2
                step = bend
            else:
                def ok(al):
                    return max(dists(al)) <= -0.05
                step = -bend
            al = bend
            if not ok(al):
                hi_ = next((bend + k * step for k in range(1, 9) if ok(bend + k * step)), None)
                if hi_ is not None:
                    lo_ = hi_ - step
                    for _ in range(12):
                        mid_ = 0.5 * (lo_ + hi_)
                        if ok(mid_):
                            hi_ = mid_
                        else:
                            lo_ = mid_
                    al = hi_
            return at(al)

        p = self.add(Panel(name, piece, "panel", [poly], asm, par.name, None, label))
        if p is not None:
            p.free = True  # (posed opening by opening, behind the panel it tucks under)

    def _boxend_pull(self, m, host, wall, piece, uid, lab, w, hh, y0, tb):
        """The 45 degree fold that pulls the box up, from the other page."""
        # ---- the 45 degree fold that pulls it up, from the other page
        g = float(m.get("brace_size", 15.0) or 15.0)
        room = min(hh, 0.5 * w - 1.0)
        if g > room + 1e-6:
            g = max(2.0, room)
            self.warn(f"{lab}: 45° fold made {g:.0f} mm to fit the wall")
        hf = Host(self, host.p1, 0.0, 0.0, wall.name, 0.0, 0.0, f"{lab}: pulling corner",
                  host.T1, Matrix.Translation((0.0, -y0, 0.0))).finish()
        hf.trig = False
        n0 = len(self.order)
        self._brace(uid, 0, hf, y0 + 0.5 * w, g, 1.0, min(tb, 0.5 * g), f"{lab}: 45° fold",
                    free_y=True)
        for name in self.order[n0:]:
            hg = self.panels[name].hinge
            if hg is not None:
                if hg.kind in ("LINEAR", "SPHERICAL", "EXPR"):
                    hg.kind = "TABLE"
                hg.kink_ok = True
