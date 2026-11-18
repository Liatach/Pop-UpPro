"""180 degree cubes, and the tower roofs and collars a cube can carry."""
import math

from mathutils import Matrix, Vector

from .base import Hinge, Host, Panel, Piece, T_MIN, TAB_LIFT
from .geom import Z, clip_halfplane, frame, hinge_frame_2d, v3


class Cubes:
    """Cube builders. Mixed into Model (model.py)."""

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
        self.match_lift(f"{piece}.B", f"{piece}.C")

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
        troof = m.get("roof", "NONE")
        if troof != "NONE" or (m.get("collar") and m.get("collar_dir") == "IN"):
            lid = "NONE"  # (the tower roof or tapered top takes its place)
        if lid == "STRUT":
            self._strut_lid(m, piece, parts, host, wB, wC, hgt, s1, s2, s3, lab)
            lid = "NONE"
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
        if troof != "NONE" or m.get("collar"):
            self._cube_tower(m, piece, parts, wB, wC, hgt, troof)

    def _strut_lid(self, m, piece, parts, host, wB, wC, hgt, s1, s2, s3, lab):
        """A flat lid hinged on one front wall's top, and a strut inside the
        box glued to that wall's page parallel to the wall's foot, F in from
        it, and up under the lid F out from its hinge. Wall, strut, page and
        lid make a parallelogram: the lid stays parallel to the page, shut on
        the box open flat, lifting off it as the card closes (the box leans
        and folds flat under it), and lies on the page shut."""
        left = m.get("strut_side", "L") != "R"
        wall = self.panels[f"{piece}.{'B' if left else 'C'}"]
        tabw = self.panels[f"{piece}.Tab{'L' if left else 'R'}"]
        page = host.p1 if left else host.p2
        wW, wD = (wB, wC) if left else (wC, wB)  # (the wall's width; the lid's depth)
        F = float(m.get("strut_at", 0.0) or 0.0) or round(min(0.5 * wD, 0.35 * wW), 1)
        if not 2.0 <= F <= wD - 2.0:
            F = max(2.0, min(F, wD - 2.0))
            self.warn(f"{lab}: the strut must stand inside the box; moved to {F:.0f} mm in")
        tbs = max(2.5, min(float(m.get("tab", 10.0) or 10.0), 0.6 * F, 0.5 * hgt,
                           wD - F - 1.0))
        # (its foot F + its tab + 2 mm out along the wall from the front
        # corner: moved F across into the box, it and its tab stay on its page)
        ws = max(3.0, min(0.3 * wW, wW - F - tbs - 2.5))
        d0 = min(F + tbs + 1.5, wW - ws - 1.0)
        if d0 < F + tbs + 0.5 or ws < 3.0:
            self.warn(f"{lab}: no room for the strut on its page (make the wall wider, or "
                      f"Strut In From Wall smaller); left off")
            return
        sgn = {}

        cache = {}

        def lid_frame(t):
            """(hinge corner, the hinge's direction away from it, across the
            lid, the strut's top - its foot) at t. The lid stays parallel to
            its page until its far edge would reach the other page; then
            that page holds it up, the lid turning further open on its hinge
            and the strut leaning with it (its top sliding a little along
            under the lid: paper gives that much)"""
            v = cache.get(t)
            if v is not None:
                return v
            c, uL, uR, P3 = parts(t)
            u, o = (uL, uR) if left else (uR, uL)
            dd = host.dirs(t)
            S, nX, nY = dd[0], dd[4 if left else 5], dd[5 if left else 4]
            f = nX.cross(u).normalized()
            if "f" not in sgn:  # (fixed open flat: across the box's top)
                cf, uLf, uRf, _ = parts(self.tmax)
                uf, of = (uLf, uRf) if left else (uRf, uLf)
                ff = host.dirs(self.tmax)[4 if left else 5].cross(uf)
                sgn["f"] = 1.0 if ff.dot(of) > 0 else -1.0
            f = sgn["f"] * f
            fp = f  # (parallel to the page: the strut's foot is F along it)
            Q = P3 + hgt * c
            # the far edge's two corners, kept clear of the other page
            g_ = u.cross(f)
            if g_.dot(nY) < 0:
                g_ = -g_  # (turning further open lifts the far edge off it)
            cl, cr, cnl, cnr = self.dirs(t)  # (and the card's own pages)

            S0_ = P3 + F * fp  # (the strut's foot)

            def clear(th):  # (the far edge's worst clearance of either page)
                fr = math.cos(th) * f + math.sin(th) * g_
                if abs((Q - S0_).dot(u.cross(fr).normalized())) > hgt + 1e-6:
                    return -1e9  # (the strut can't reach the lid there)
                return min(min((K - S).dot(nY), (K - S).dot(nX), K.dot(cnl), K.dot(cnr))
                           for K in (Q + wD * fr, Q + wW * u + wD * fr))

            th = 0.0
            if clear(0.0) < 0.6:  # (pushed open by the other page; as clear as can be)
                best = clear(0.0)
                for k in range(1, 91):  # (the least turn, either way, that clears)
                    for x in (math.radians(k), -math.radians(k)):
                        cx = clear(x)
                        if cx > best + 1e-6:
                            best, th = cx, x
                    if best >= 0.6:
                        break
            f = math.cos(th) * f + math.sin(th) * g_
            # the strut: the wall's height, from its foot F across the page,
            # turned to meet the lid
            Wf = P3
            h0 = hgt * c
            S0 = Wf + F * fp
            n_l = u.cross(f).normalized()
            hp = u.cross(h0)
            a_, b_ = h0.dot(n_l), hp.dot(n_l)
            cc = (Q - S0).dot(n_l)
            R = math.hypot(a_, b_)
            psi = 0.0
            if R > 1e-9 and abs(cc - a_) > 1e-6:
                phi = math.atan2(b_, a_)
                k = max(-1.0, min(1.0, cc / R))
                psi = min((phi + math.acos(k), phi - math.acos(k)),
                          key=lambda x: abs((x + math.pi) % (2.0 * math.pi) - math.pi))
                psi = (psi + math.pi) % (2.0 * math.pi) - math.pi
            v = (Q, u, f, S0 - Wf, psi)
            if len(cache) > 4096:
                cache.clear()
            cache[t] = v
            return v

        def pat(o):
            return frame(v3(o), (1, 0, 0), (0, 1, 0)).inverted()

        if left:  # (B runs s1..s2 in its pattern, +x towards the front corner)
            poly = [(s1, hgt), (s2, hgt), (s2, hgt + wD), (s1, hgt + wD)]

            def asm_lid(t):
                P, u, f = lid_frame(t)[:3]
                return frame(P, -u, f) @ pat((s2, hgt))
        else:  # (C runs s2..s3, +x away from it)
            poly = [(s2, hgt), (s3, hgt), (s3, hgt + wD), (s2, hgt + wD)]

            def asm_lid(t):
                P, u, f = lid_frame(t)[:3]
                return frame(P, u, f) @ pat((s2, hgt))
        lid = self.add(Panel(f"{piece}.Lid", piece, "panel", [poly], asm_lid, wall.name,
                             None, f"{lab}: lid"))
        lid.free = True
        # the strut: the wall's own pose, moved F across its page into the box
        xa = (s2 - d0 - ws) if left else (s2 + d0)
        sp = f"{piece}S"
        self.add_piece(Piece(sp, f"{lab} strut", 1 + m["uid"], (xa + 0.5 * ws, 0.5 * hgt)))

        def shift(t):
            return Matrix.Translation(lid_frame(t)[3])

        def asm_strut(t):  # (the wall's pose moved across, turned psi on its foot)
            Q, u, f, d, psi = lid_frame(t)
            P3 = parts(t)[3]
            S0 = P3 + d
            return Matrix.Translation(S0) @ Matrix.Rotation(psi, 4, u) @ \
                Matrix.Translation(-S0) @ shift(t) @ wall.asm(t)

        def asm_c(t):
            return shift(t) @ tabw.asm(t)

        def asm_e(t):  # (under the lid, where the strut's top meets it)
            Q, u, f, d, psi = lid_frame(t)
            top = asm_strut(t) @ v3((xa, hs))
            dist = (top - Q).dot(f)
            A = asm_lid(t)
            n = (A.to_3x3() @ Vector((0.0, 0.0, 1.0))).normalized()
            c, uL, uR, P3 = parts(t)
            inside = P3 + 0.5 * hgt * c + 0.5 * (wB * uL + wC * uR)
            if n.dot(inside - lid_frame(t)[0]) > 0:
                n = -n
            # (folded back under it, towards the hinge, its face down)
            return Matrix.Translation(-3.0 * TAB_LIFT * n) @ A @ \
                Matrix.Translation((0.0, dist + hgt, 0.0)) @ Matrix.Rotation(math.pi, 4, "X") @ \
                Matrix.Translation((0.0, -hs, 0.0))

        hs = hgt - 2.0 * TAB_LIFT  # (its top a paper's thickness under the lid)
        stp = self.add(Panel(f"{sp}.Strut", sp, "panel",
                             [[(xa, 0.0), (xa + ws, 0.0), (xa + ws, hs), (xa, hs)]],
                             asm_strut, page, None, f"{lab}: strut"))
        stp.free = True
        # tab C: like the wall's own base tab, on the same side of the foot
        tpoly = tabw.polys[0]
        down = min(q[1] for q in tpoly) < 0
        ch = min(0.3 * tbs, 0.2 * ws)
        yv = -tbs if down else tbs
        self.add(Panel(f"{sp}.TabC", sp, "tab",
                       [[(xa + ch, yv), (xa, 0.0), (xa + ws, 0.0), (xa + ws - ch, yv)]],
                       asm_c, page, None, f"{lab}: strut's foot tab"))
        te = self.add(Panel(f"{sp}.TabE", sp, "tab",
                       [[(xa, hs), (xa + ws, hs), (xa + ws - ch, hs + tbs),
                         (xa + ch, hs + tbs)]], asm_e, lid.name, None,
                       f"{lab}: strut's top tab (under the lid)"))
        te.free = True  # (it slides a little along under the lid as the strut leans)

    def _cube_tower(self, m, piece, parts, wB, wC, hgt, troof):
        """A tower's roof (pointed or flat) or collar on a cube: the cube is a
        tower whose front corner closes on the fold, like a castle's crease
        tower, so the same V-folds and collars go on it. Its front walls are
        the corner's two walls; its back walls the tower's inner ones."""
        lab = m["label"]
        tr = min(90.0, 0.5 * self.tmax)
        c, uL, uR, P3 = parts(tr)
        names = {"B": f"{piece}.B", "C": f"{piece}.C", "A": f"{piece}.A", "D": f"{piece}.D"}
        P = self.panels

        def T_on(pn, O, x_dir, y_dir):
            """Virtual (x along x_dir, y up) -> panel pn's pattern, from where
            it is at the reference opening (it moves rigidly with it)."""
            return P[pn].asm(tr).inverted() @ frame(O, x_dir, y_dir)

        best = None
        for left, right, ul, ur, wl, wr in (("C", "B", uR, uL, wC, wB),
                                            ("B", "C", uL, uR, wB, wC)):
            T1 = T_on(names[left], P3, -ul, c)
            T2 = T_on(names[right], P3, ur, c)
            h = Host(self, names[left], 0.0, 0.0, names[right], 0.0, 0.0,
                     f"{lab}: tower", T1, T2)
            S, l, r, Y, nl, nr = h.dirs(tr)
            if nl.dot(l + r) > 0 and nr.dot(l + r) > 0:  # (normals in, like a tower's)
                best = (h, left, right, wl, wr)
                break
        if best is None:
            return
        h, left, right, a, b = best
        h.finish()
        h.tower_top = 0.0
        h.key = m["uid"]
        # the inner walls: from A (a along l) on toward r, and from B back
        Cpt = P3 + a * (uR if left == "C" else uL) + b * (uL if left == "C" else uR)
        AC = names["D"] if left == "C" else names["A"]
        CB = names["A"] if left == "C" else names["D"]
        l_, r_ = (uR, uL) if left == "C" else (uL, uR)
        # at the back corner C: left along AC back to A (-r), right along CB to B (-l)
        TC = (T_on(AC, Cpt, r_, c), T_on(CB, Cpt, -l_, c))
        base = f"{piece}t"
        self.__dict__.setdefault("_tw", {})[base] = dict(AC=AC, CB=CB, TC=TC)
        self.placed[m["uid"]] = h
        # (their tabs glue over the cube's closing tab at the back corner)
        for w_ in ("roof", "collar"):
            self.stack_ok.add(frozenset((lab, f"{lab} {w_}")))
        if troof == "GABLE":  # (Birmingham 49: the pop-up house)
            self._tower_gable(m, h, base, a, b, 0.0, hgt, float(m.get("tab", 10.0)))
        if troof in ("POINTED", "FLAT"):
            mm = dict(m, roof_below=0.0)
            self._tower_roof(mm, h, base, a, b, 0.0, hgt, float(m.get("tab", 10.0)),
                             flat=troof == "FLAT")
        if m.get("collar"):
            self._tower_collar(m, h, base, a, b, 0.0, hgt, float(m.get("tab", 10.0)))
