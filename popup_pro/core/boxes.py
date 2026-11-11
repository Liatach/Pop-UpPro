"""Box folds: square and angled, straps, box layers, with their railings
and balcony supports."""
import math

from mathutils import Matrix, Vector

from .base import arcade, Hinge, Host, Panel, Piece, T_MIN, TAB_LIFT
from .geom import ccw, clip_halfplane, frame, hinge_frame_2d


class BoxFolds:
    """Box fold builders. Mixed into Model (model.py)."""

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
        if abs(float(m.get("fan_angle", 0.0) or 0.0)) > 0.05:
            if m.get("style") == "CUT" or getattr(host, "tower_top", None) is not None:
                self.warn(f"{lab}: angled glue lines need a glued box fold (not a box "
                          f"layer or a tower); made square")
            else:
                self._angled_box(m, host)
                return

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
        if m.get("support", "SOLID") == "ARCHES" and m.get("style") != "CUT" and single:
            self._supports(m, base, a, b, w, k)
        rail = float(m.get("rail", 0.0) or 0.0)
        if rail > 1e-6:
            self._rail(m, host, base, a, b, y0, w, k, rail, single)
        tri = m.get("tri45", "NONE") or "NONE"
        if tri != "NONE" and (uid, "C") in self.hosts:
            self._tri45(m, self.hosts[(uid, "C")], tri, y0, w, a, b, k, base, lab)
        if getattr(host, "tower_top", None) is not None and m.get("style") != "CUT":
            # a tower in a tube's corner: the walls are its outer faces. Its
            # tabs may lie over the tube's closing tab (glue on glue is fine)
            tube_lab = next((x["label"] for x in self.mechs if x["uid"] == host.key), None)
            if tube_lab:
                self.stack_ok.add(frozenset((tube_lab, lab)))
            for n in (f"{base}.AC", f"{base}.CB"):
                if n in self.panels:  # never flat on its fold: no resting lift
                    self.panels[n].lift = 0.0
            if y0 + w > host.tower_top + 1e-6:
                self._raise_walls(host, a, b, y0 + w)
            taper = m.get("collar") and m.get("collar_dir") == "IN"
            if taper and m.get("roof", "NONE") != "NONE":
                self.warn(f"{m['label']}: a tapered top takes the roof's place; no roof")
            elif m.get("roof") in ("POINTED", "FLAT"):
                self._tower_roof(m, host, base, a, b, y0, w, float(m.get("tab", 10.0)),
                                 flat=m.get("roof") == "FLAT")
            elif m.get("roof") == "GABLE":
                self._tower_gable(m, host, base, a, b, y0, w, float(m.get("tab", 10.0)))
            if m.get("collar"):
                self._tower_collar(m, host, base, a, b, y0, w, float(m.get("tab", 10.0)))

    # ------------------------------------------------------- angled box folds
    @staticmethod
    def _cones(u1, c1, u2, c2, sgn):
        """Unit direction d with d . u1 = c1 and d . u2 = c2 (two cones, or a
        cone and a plane), on the branch sgn. None if they don't meet."""
        g = u1.dot(u2)
        det = 1.0 - g * g
        if det < 1e-12:
            return None, 0.0
        p = (c1 - c2 * g) / det
        q = (c2 - c1 * g) / det
        base = p * u1 + q * u2
        k2 = 1.0 - base.length_squared
        k = math.sqrt(max(0.0, k2))
        return (base + sgn * k * u1.cross(u2).normalized()).normalized(), k2

    def _angled_box(self, m, host):
        """Kim's angled box fold: the strip's glue lines turned, mirrored either
        side of the fold, so they meet the fold (at O) above or below the strip;
        its crease (or three: two with a free middle between them, and one
        down the middle's centre) meets there too, so every fold of it turns
        about O. One crease: the box fold's crease, the strip a V-fold glued
        away from its point. Three: the middle spans the gap like a shelf,
        then folds down its centre as the card shuts."""
        uid, lab = m["uid"], m["label"]
        W, H = self.W, self.H
        a, y0, w = float(m["height"]), float(m["y"]), float(m["width"])
        th = math.radians(max(-70.0, min(70.0, float(m["fan_angle"]))))
        sg = 1.0 if th > 0 else -1.0
        T = abs(th)
        two = m.get("fan_creases", "ONE") == "THREE"
        be = float(m.get("fan_crease", 0.0) or 0.0)
        be = math.radians(be) if be > 0.05 else (0.5 * T if two else T)
        if be < (0.5 * T if two else T) - 1e-6:
            self.warn(f"{lab}: crease angle smaller than {'half ' if two else ''}the glue "
                      f"angle tears as the card opens; made {'half ' if two else ''}the "
                      f"glue angle")
            be = 0.5 * T if two else T
        if abs(float(m.get("depth", a)) - a) > 0.05 and not m.get("strap"):
            pass  # (angled: the two sides mirror each other, both Height out)
        psi, mu = (2.0 * be, be) if two else (be, 0.0)  # glue and crease, off the axis
        if psi >= math.radians(85.0):
            self.warn(f"{lab}: crease angle too wide; made narrower")
            be = math.radians(85.0) / (2.0 if two else 1.0)
            psi, mu = (2.0 * be, be) if two else (be, 0.0)
        # O on the fold: the glue lines meet there, distance d along it from O
        dn = a / math.tan(T)  # to the strip's bottom (sg > 0) or top edge
        yO = y0 - sg * dn
        if sg > 0:
            d1, d2 = dn, dn + w
        else:
            d1, d2 = dn - w, dn
            if d1 < 3.0:
                d1 = min(3.0, d2 - 3.0)
                self.warn(f"{lab}: its glue lines meet below its top; shortened")
        s1, s2 = d1 / math.cos(T), d2 / math.cos(T)  # along the glue lines
        if min(y0, y0 + w) < -1e-6 or max(y0, y0 + w) > H + 1e-6:
            self.warn(f"{lab}: runs past the top or bottom of the card")
        if a + s2 * math.sin(T) - a > W and host.is_spine:
            self.warn(f"{lab}: wider than the page")
        base = f"Box{uid}"
        piece = base
        self.add_piece(Piece(piece, lab, 1 + uid, (0.0, 0.5 * (s1 + s2))))

        def u2(ang):  # pattern direction ang off the axis (+Y), X mirrored by sg
            return Vector((sg * math.sin(ang), math.cos(ang), 0.0))
        gLp, gRp, c1p, c2p = u2(-psi), u2(psi), u2(-mu), u2(mu)
        Y1, Y2 = s1 * math.cos(psi), s2 * math.cos(psi)  # the strip's edges, across the axis

        def on(u, Yv):  # where the line along u meets the edge Y' = Yv
            return (u.x * Yv / u.y, Yv)
        lines = [gLp, c1p, Vector((0.0, 1.0, 0.0)), c2p, gRp] if two else [gLp, c1p, gRp]
        polys = [[on(lines[i], Y1), on(lines[i + 1], Y1), on(lines[i + 1], Y2),
                  on(lines[i], Y2)] for i in range(len(lines) - 1)]

        def pf(u, v):
            return frame((0.0, 0.0, 0.0), u, v)
        Fp = [pf(lines[i], lines[i + 1]).inverted() for i in range(len(lines) - 1)]

        def page(t):
            t = max(T_MIN, t)
            S, l, r, Y, nl, nr = host.dirs(t)
            O = S + yO * Y
            dL = (math.cos(T) * sg * Y + math.sin(T) * l).normalized()
            dR = (math.cos(T) * sg * Y + math.sin(T) * r).normalized()
            n = l - r
            n = n.normalized() if n.length > 1e-9 else nl.normalized()
            return O, dL, dR, n, l, r, Y, nl, nr

        cb, sb = math.cos(be), math.sin(be)
        cm = math.cos(2.0 * mu)
        tr = max(30.0, min(120.0, self.t_ref))
        O, dL, dR, n, l, r, Y, nl, nr = page(tr)
        gap = (l + r).normalized()
        # the branch reaching into the gap between the pages
        s0 = math.sin(mu)
        sym = max((1.0, -1.0), key=lambda s_: self._cones(dL, cb, n, s0, s_)[0].dot(gap))

        def c_sym(t):
            O, dL, dR, n, *_ = page(t)
            c1, k2 = self._cones(dL, cb, n, s0, sym)
            c2 = c1 - 2.0 * c1.dot(n) * n  # its mirror image
            return O, dL, dR, c1, c2, k2

        tears = [t for t in self.samples if c_sym(t)[5] < -1e-6]
        if tears:
            self.warn(f"{lab}: tears if opened past {min(tears):.0f} degrees (make the "
                      f"crease angle bigger)")
        t_s = None
        if two:
            # The middle spans the gap like a shelf while the card is well
            # open; closing further, it would push into the pages. From the
            # opening where its sides reach them, the side panels lie flat on
            # their pages and the middle folds down its centre crease, a
            # V-fold between them, until it all lies flat shut.
            def f(t):
                return c_sym(t)[3].dot(page(t)[7])
            lo, hi = T_MIN, max(T_MIN, tr)
            if f(hi) > 0 and f(lo) < 0:
                for _ in range(50):
                    mid = 0.5 * (lo + hi)
                    if f(mid) < 0:
                        lo = mid
                    else:
                        hi = mid
                t_s = hi
                S, l, r, Y, nl, nr = host.dirs(t_s)
                c1 = c_sym(t_s)[3]
                cl = (c1.dot(l), c1.dot(Y))  # its place on the left page
                tl = max(T_MIN, t_s - 1.0)
                O_, dL_, dR_, n_, l_, r_, Y_, nl_, nr_ = page(tl)
                c1x = (cl[0] * l_ + cl[1] * Y_).normalized()
                cbr = max((1.0, -1.0), key=lambda s_: self._cones(
                    c1x, math.cos(mu), n_, 0.0, s_)[0].dot(nl_ + nr_))

        def dirs_at(t):
            if t_s is not None and t < t_s:
                O, dL, dR, n, l, r, Y, nl, nr = page(t)
                c1 = (cl[0] * l + cl[1] * Y).normalized()
                c2 = (cl[0] * r + cl[1] * Y).normalized()
                ax = self._cones(c1, math.cos(mu), n, 0.0, cbr)[0]
                return O, dL, dR, c1, ax, c2
            O, dL, dR, c1, c2, _ = c_sym(t)
            return O, dL, dR, c1, (c1 + c2).normalized(), c2

        cache = {}

        def solved(t):
            v = cache.get(t)
            if v is None:
                O, dL, dR, c1, ax, c2 = dirs_at(t)
                L3 = [dL, c1, ax, c2, dR] if two else [dL, c1, dR]
                v = [frame(O, L3[i], L3[i + 1]) @ Fp[i] for i in range(len(L3) - 1)]
                if len(cache) > 4096:
                    cache.clear()
                cache[t] = v
            return v

        names = ["AC", "MidL", "MidR", "CB"] if two else ["AC", "CB"]
        txts = ["glued left", "middle left", "middle right", "glued right"] if two \
            else ["top", "front"]
        parent = host.p1
        prev = None
        for i, nm in enumerate(names):
            asm = (lambda t, i=i: solved(t)[i])
            Fc = hinge_frame_2d((0.0, 0.0), (lines[i].x, lines[i].y))
            pa = self.panels[parent].asm
            Hp = pa(tr).inverted() @ asm(tr) @ Fc
            hg = Hinge(Hp, Fc, "TABLE")
            hg.kink_ok = True
            prev = self.add(Panel(f"{base}.{nm}", piece, "panel", [polys[i]], asm, parent,
                                  hg, f"{lab}: {txts[i]}"))
            if prev is None:
                self.warn(f"{lab}: too small to fold")
                return
            parent = prev.name
        if not two and abs(be - T) < 1e-6:
            th_ = float(self.card.get("thickness", 0.0) or 0.0)
            self.panels[f"{base}.AC"].lift = (TAB_LIFT + 2.0 * th_ + 0.05 if th_ > 0
                                              else 2.0 * TAB_LIFT) * host.lift[0]
        # glue tabs: folded back under the strip, flat on the pages
        t_ = float(m.get("tab", 12.0))
        ch = min(0.3 * t_, 0.25 * (s2 - s1))
        for side, gp, nb, par, Tp, k_ in (("A", gLp, lines[1], host.p1, host.T1, 0),
                                          ("B", gRp, lines[-2], host.p2, host.T2, 1)):
            v_ = Vector(on(nb, Y1) + (0.0,)) - Vector(on(gp, Y1) + (0.0,))
            out = Vector((-gp.y, gp.x, 0.0))
            if out.dot(v_) > 0:
                out = -out  # (away from the strip)
            P1_, P2_ = gp * s1, gp * s2
            poly = [(P1_.x, P1_.y), (P2_.x, P2_.y),
                    ((P2_ + t_ * out - ch * gp).x, (P2_ + t_ * out - ch * gp).y),
                    ((P1_ + t_ * out + ch * gp).x, (P1_ + t_ * out + ch * gp).y)]
            sx = -1.0 if side == "A" else 1.0
            gv = Vector((sx * math.sin(T), sg * math.cos(T), 0.0))  # glue line, virtual
            inw = Vector((-gv.y, gv.x, 0.0))
            if inw.x * sx > 0:
                inw = -inw  # (toward the fold)
            lift = host.lift[k_]
            Tv = frame(Vector((0.0, yO, lift * TAB_LIFT)), gv, inw) @ pf(gp, out).inverted()
            # stay on this side of the fold
            n2 = (sx * Tv[0][0], sx * Tv[0][1])
            poly = clip_halfplane(poly, n2, 0.5 - sx * Tv[0][3])
            Tpat = Tp @ Tv
            pa = self.panels[par].asm
            self.add(Panel(f"{base}.Tab{side}", piece, "tab", [poly],
                           (lambda t, pa=pa, T_=Tpat: pa(t) @ T_), par, None,
                           f"{lab}: tab {side}"))
        self.line_frames[uid] = (piece, lambda q: q, None)
        for nm_ in ("rail", "peaks", "tri45"):
            v_ = m.get(nm_)
            if v_ and v_ not in ("NONE", 1, 1.0, 0, 0.0):
                self.warn(f"{lab}: {'railing' if nm_ == 'rail' else nm_.replace('tri45', '45° triangles')} "
                          f"isn't made on an angled box fold")
                break

    def _rail(self, m, host, base, a, b, y0, w, k, rail, single):
        """A balcony's railing: a strip stuck flat on the outside of a box
        fold's front (the leg under the floor), standing rail above its top
        (the floor). It moves with the front, so it folds flat with it."""
        lab, uid = m["label"], m["uid"]
        CB = f"{base}.CB"
        if not single or CB not in self.panels:
            self.warn(f"{lab}: a railing needs a plain box fold (one peak); no railing")
            return
        if abs(k) > 1e-9:
            self.warn(f"{lab}: a railing on a slanted box fold isn't made; no railing")
            return
        if host.is_spine and a + b + rail > self.W + 1e-6:
            self.warn(f"{lab}: the railing sticks out of the card when it's shut")
        piece = f"Rail{uid}"
        self.add_piece(Piece(piece, f"{lab} railing", 900 + uid, (0.5 * (a + rail), 0.5 * w)))
        # pattern: x up the front from its foot (B, 0) past the top (C, a);
        # y along the fold
        polys = [[(0.0, 0.0), (a + rail, 0.0), (a + rail, w), (0.0, w)]]
        if m.get("support", "SOLID") == "ARCHES":
            # (glued only on the band above the arches)
            tb_ = self._arch_bands(a, w)[0]
            polys = [[(a - tb_, 0.0), (a + rail, 0.0), (a + rail, w), (a - tb_, w)]]
        if m.get("rail_open") and rail >= 6.0:
            # posts between a top rail and a strip along the floor
            n = max(1, int(round(w / 7.0)))
            band = min(2.5, 0.25 * rail)
            bars = arcade(rail, w, n, band, 1.5, min(2.0, 0.3 * w / n), arch=False)
            if bars:
                low = polys[0][0][0]
                polys = [[(low, 0.0), (a, 0.0), (a, w), (low, w)]] + \
                    [[(a + rail - s_, v) for s_, v in q] for q in bars]

        def asm_own(t):
            S, l, r, Y, nl, nr = host.dirs(t)
            out = (r - r.dot(l) * l).normalized()  # away from the wall it's against
            return frame(S + b * r + y0 * Y + TAB_LIFT * out, l, Y)

        cb = self.panels[CB]
        tr = self.t_ref
        off = cb.asm(tr).inverted() @ asm_own(tr)

        def asm(t, f=cb.asm, off=off):
            return f(t) @ off

        self.add(Panel(f"{piece}.Rail", piece, "panel", polys, asm, CB, None,
                       f"{lab}: railing"))

    @staticmethod
    def _arch_bands(a, w):
        """A balcony's arcade under its floor: band over the arches, sill, pillar."""
        return max(2.0, 0.15 * a), max(1.5, 0.08 * a), max(2.0, min(4.0, 0.08 * w))

    def _supports(self, m, base, a, b, w, k):
        """Cut a box fold's front (a balcony's support) into arches."""
        lab = m["label"]
        CB = f"{base}.CB"
        if CB not in self.panels or abs(k) > 1e-9:
            self.warn(f"{lab}: arches need a plain box fold (one peak, no slant)")
            return
        top, sill, pil = self._arch_bands(a, w)
        bays = int(m.get("bays", 3) or 3)
        parts = arcade(a, w, bays, top, sill, pil)
        if parts is None:
            self.warn(f"{lab}: too small for {bays} arches; left solid")
            return
        # front pattern: u from C (b, the top) to B (a + b, the foot), v along
        self.panels[CB].polys = [ccw([(b + s_, v) for s_, v in q]) for q in parts]
