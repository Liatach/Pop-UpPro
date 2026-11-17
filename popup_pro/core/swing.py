"""Arm behind a mask (Birmingham 75): a picture swings round in its own
plane, its pivot hidden behind a mask, as the card opens.

The mask is a layer parallel to one side of a fold, its tab B glued on the
other side A from the fold (a parallelogram, like a stand-up's). A small
hinge joins it to the side it's parallel to: two A x A squares side by side,
each cut by a diagonal from its outer top corner to the middle of the
bottom edge, with a crease up the middle. Its tab D is glued on the page,
its tab E on the back of the mask. As the mask's offset from the page turns
through the card's opening, the hinge folds up on its diagonals, and the
triangle by tab D's top corner (C) turns a right angle in its own plane
about that corner: the arm glued on it swings with it. Open flat, the
hinge lies flat; closed, it's folded flat.

model.py has the module's overview and the Model class."""
import math

from mathutils import Matrix, Vector

from .base import Host, Panel, Piece, TAB_LIFT
from .geom import clip_halfplane, frame


def _tri(P, W):
    """The rigid map taking pattern triangle P (2D) onto world triangle W."""
    p = [Vector((q[0], q[1], 0.0)) for q in P]
    return frame(W[0], W[1] - W[0], W[2] - W[0]) @ frame(p[0], p[1] - p[0],
                                                       p[2] - p[0]).inverted()


def _crosses(A, B, eps=0.05):
    """Do two convex polygons (3D points) cut through each other? (an edge
    of one passing through the other's inside, not just touching it)"""
    def through(a, b, P):
        n = (P[1] - P[0]).cross(P[2] - P[0])
        if n.length < 1e-9:
            return False
        n.normalize()
        da, db = (a - P[0]).dot(n), (b - P[0]).dot(n)
        if da * db > 0 or min(abs(da), abs(db)) < eps:
            return False
        x = a + (b - a) * (da / (da - db))
        return all((P[(i + 1) % len(P)] - P[i]).cross(x - P[i]).dot(n) >
                   0.3 * (P[(i + 1) % len(P)] - P[i]).length for i in range(len(P)))
    return any(through(X[i], X[(i + 1) % len(X)], Y)
               for X, Y in ((A, B), (B, A)) for i in range(len(X)))


class Swing:
    """Arm-behind-a-mask builder. Mixed into Model (model.py)."""

    def _swing(self, m, host):
        uid, lab = m["uid"], m["label"]
        g = max(4.0, float(m.get("swing_gap", 20.0) or 20.0))  # A: square, mask's offset
        F = float(m.get("swing_at", 0.0) or 0.0) or 2.0 * g + 15.0  # tab D's fold from the fold
        y_h = float(m.get("y", 60.0))  # the hinge's bottom, up the fold
        tab = max(3.0, min(float(m.get("tab", 8.0) or 8.0), g))
        Wm = float(m.get("width", 0.0) or 0.0)
        Wm = Wm if Wm >= 5.0 else F + g + tab + 8.0  # the mask, from B
        Hm = float(m.get("height", 0.0) or 0.0)
        Hm = Hm if Hm >= 5.0 else g + 24.0
        La = float(m.get("arm_len", 0.0) or 0.0) or 2.5 * g
        wa = float(m.get("arm_hand", 0.0) or 0.0) or g
        on_left = m.get("swing_side", "R") == "L"
        ccw_ = m.get("swing_dir", "CW") == "CCW"
        if F < 2.0 * g + 2.0:
            F = 2.0 * g + 2.0
            self.warn(f"{lab}: the hinge must clear the fold; moved out to {F:.0f} mm")
        if Wm < F + g:
            self.warn(f"{lab}: the mask doesn't hide the hinge (make it at least "
                      f"{F + g:.0f} mm wide)")
        x0 = F - 2.0 * g  # the hinge's tab E fold, from the fold, open flat
        # the base side carries the hinge; the other carries tab B. On the
        # left the frame runs down the fold so that it stays right-handed.
        base, other = (host.p1, host.p2) if on_left else (host.p2, host.p1)
        q0 = -(y_h + g) if on_left else y_h
        # the hinge as drawn turns clockwise as the card opens, seen from the
        # front (on the left too: there it's the right's turned half round);
        # drawn upside down, its diagonals meeting at the top, the other way
        flip = ccw_
        # open flat everything lies stacked on the page: the hinge a little
        # off it, the mask over the hinge and the arm (shown only; the hinge
        # is lifted whole, so its own shape is exact)
        def lift(c):
            return TAB_LIFT * max(0.0, -c)
        Lc = 3.0 * TAB_LIFT  # (the mask: a steady lift, so its fold B stays a true hinge)

        def dirs(t):
            S, l, r, Y, nl, nr = host.dirs(t)
            if on_left:
                rb, Yb, od = l, -Y, r
            else:
                rb, Yb, od = r, Y, l
            nb = rb.cross(Yb)
            return S, rb, Yb, nb, od

        def Fb(t):
            S, rb, Yb, nb, od = dirs(t)
            return frame(S + x0 * rb + q0 * Yb + lift(od.dot(rb)) * nb, rb, Yb)

        def q_(v):  # (drawn upside down: q mirrored in the square's middle)
            return Vector((v[0], g - v[1], v[2])) if flip else v

        def p_(P):
            return [(x, g - y) if flip else (x, y) for x, y in P]

        cache = {}

        def solve(t):
            """The hinge's corners in the base frame: V (the diagonals'
            meeting point, on the bottom edge), T (the crease's top), PR
            (tab D's top corner), PL (tab E's), E (tab E's bottom corner),
            and the mask's offset."""
            v = cache.get(t)
            if v is not None:
                return v
            S, rb, Yb, nb, od = dirs(t)
            c, s = od.dot(rb), od.dot(nb)
            off = Vector((g * c, 0.0, g * s))
            D = Vector((2.0 * g, 0.0, 0.0))
            E = off + Vector((g, 0.0, 0.0))
            # V: on circles of radius g about D's and E's bottom corners; not
            # the plain fold up the middle but its mirror across D-E
            th = math.atan2(s, c)
            dd = Vector((-math.sin(0.5 * th), 0.0, math.cos(0.5 * th)))
            if (E - D).length > 1e-6:
                dd = (E - D).normalized()
            w = Vector((g, 0.0, 0.0)) - D
            V = D + 2.0 * w.dot(dd) * dd - w
            if (E - D).length > 2.0 * g:  # (flat, with the mask's lift)
                V = 0.5 * (D + E)
            PR = Vector((2.0 * g, g, 0.0))
            PL = E + Vector((0.0, g, 0.0))
            # T: g from V, PR and PL
            ex = PR - V
            d1 = ex.length
            ex.normalize()
            i = ex.dot(PL - V)
            ey = PL - V - i * ex
            if ey.length < 1e-9:
                ey = Vector((0.0, 1.0, 0.0)) - Vector((0.0, 1.0, 0.0)).dot(ex) * ex
            ey.normalize()
            j = ey.dot(PL - V)
            ez = ex.cross(ey)
            x = 0.5 * d1
            y = (i * i + j * j - 2.0 * i * x) / (2.0 * j) if abs(j) > 1e-9 else 0.0
            z = math.sqrt(max(0.0, g * g - x * x - y * y))
            Ts = [V + x * ex + y * ey + sg * z * ez for sg in (1.0, -1.0)]
            # the branch turning C round (its corner T heading for D's line)
            T = min(Ts, key=lambda q: q.z - 1e-3 * q.x)
            v = (V, T, PR, PL, E, off)
            if len(cache) > 4096:
                cache.clear()
            cache[t] = v
            return v

        # pattern: tab E | LL UL | UR LR | tab D, the squares from x = 0 to 2g
        Vp, Tp, PRp, PLp, Eb, Dp = (g, 0.0), (g, g), (2.0 * g, g), (0.0, g), (0.0, 0.0), \
            (2.0 * g, 0.0)
        facets = (("LR", "beside tab D", (Dp, PRp, Vp), lambda s_: (s_[5], s_[2], s_[0])),
                  ("UR", "C, the arm's triangle", (Vp, PRp, Tp),
                   lambda s_: (s_[0], s_[2], s_[1])),
                  ("UL", "beside the crease", (Vp, Tp, PLp), lambda s_: (s_[0], s_[1], s_[3])),
                  ("LL", "beside tab E", (Eb, Vp, PLp), lambda s_: (s_[4], s_[0], s_[3])))
        piece = f"Swing{uid}"
        self.add_piece(Piece(piece, f"{lab} hinge", 1 + uid, (g, 0.5 * g)))
        mats = {}

        def facet_asm(key, P, Wf):
            def loc(t):
                V, T, PR, PL, E, off = solve(t)
                pts = Wf((V, T, PR, PL, E, Vector((2.0 * g, 0.0, 0.0))))
                return _tri(p_(P), [q_(q) for q in pts])
            mats[key] = loc

            def asm(t):
                return Fb(t) @ loc(t)
            return asm

        for key, txt, P, Wf in facets:
            fp = self.add(Panel(f"{piece}.{key}", piece, "panel", [p_(list(P))],
                                facet_asm(key, P, Wf), base, None,
                                f"{lab}: hinge {txt}"))
            fp.free = True
        # tab D, glued on the page beside its square; tab E on the mask's back
        ch = 0.25 * g
        pD = p_([(2.0 * g, 0.0), (2.0 * g + tab, ch), (2.0 * g + tab, g - ch), (2.0 * g, g)])
        pE = p_([(-tab, ch), (0.0, 0.0), (0.0, g), (-tab, g - ch)])
        def asm_d(t):
            S, rb, Yb, nb, od = dirs(t)  # (on the page, under the lifted hinge)
            return Fb(t) @ Matrix.Translation((0.0, 0.0, TAB_LIFT - lift(od.dot(rb))))

        def asm_e(t):  # (q mirrored alike in pattern and frame: a plain shift)
            V, T, PR, PL, E, off = solve(t)
            return Fb(t) @ Matrix.Translation(E + Vector((0.0, 0.0, TAB_LIFT)))

        self.add(Panel(f"{piece}.TabD", piece, "tab", [pD], asm_d, base, None,
                       f"{lab}: hinge tab D"))
        # the mask: its fold B on the other side g from the fold, then
        # parallel to the base side; tab B glued on beyond it
        mp = f"Mask{uid}"
        self.add_piece(Piece(mp, f"{lab} mask", 1 + uid, (0.5 * Wm, 0.5 * Hm)))
        qm = 0.5 * (g - Hm)  # (the mask's bottom, centred on the hinge)
        if flip:
            qm = g - qm - Hm
        tb = min(tab, g)

        def asm_mask(t):
            S, rb, Yb, nb, od = dirs(t)
            return frame(S + g * od + q0 * Yb + Lc * nb, rb, Yb)

        def asm_b(t):
            S, rb, Yb, nb, od = dirs(t)
            return frame(S + g * od + q0 * Yb + TAB_LIFT * (-od).cross(Yb), -od, Yb)

        # mask pattern: u from B along the base side, v the hinge's q
        mask = self.add(Panel(f"{mp}.Mask", mp, "panel",
                              [[(0.0, qm), (Wm, qm), (Wm, qm + Hm), (0.0, qm + Hm)]],
                              asm_mask, other, None, f"{lab}: mask"))
        mask.free = True
        self.add(Panel(f"{mp}.TabB", mp, "tab",
                       [[(-tb, qm + 0.2 * tb), (0.0, qm), (0.0, qm + Hm),
                         (-tb, qm + Hm - 0.2 * tb)]], asm_b, other, None,
                       f"{lab}: mask's tab B"))
        self.add(Panel(f"{piece}.TabE", piece, "tab", [pE], asm_e, mask.name, None,
                       f"{lab}: hinge tab E (on the mask's back)"))
        # the arm: its end glued on C, creased across beside the pivot, then
        # out at its angle (open flat; 0: straight out of the hinge's edge
        # beside the pivot, + anticlockwise as seen). C tilts up as the hinge
        # folds; the arm bends at its crease to lie flat between the page and
        # the mask, as the paper does when it's pressed between them
        ang = math.radians(float(m.get("swing_angle", 0.0) or 0.0))
        ap = f"SwArm{uid}"
        self.add_piece(Piece(ap, f"{lab} arm", 1 + uid, (1.5 * g, g + 0.5 * La)))
        # (worked as drawn the right way up, then mirrored like the hinge)
        du = Vector((math.sin(ang) if flip else -math.sin(ang), math.cos(ang), 0.0))
        eu = Vector((-du.y, du.x, 0.0))  # (across it, towards C)
        PRu = Vector((2.0 * g, g, 0.0))
        tri = [(g, 0.5), (2.0 * g, g), (g, g)]
        band = clip_halfplane(tri, (eu.x, eu.y), eu.x * PRu.x + eu.y * PRu.y)
        band = clip_halfplane(band, (-eu.x, -eu.y), -(eu.x * PRu.x + eu.y * PRu.y) - wa)

        def sb(q):  # (along the arm, and across it, from the pivot)
            v = Vector((q[0], q[1], 0.0)) - PRu
            return float(v.dot(du)), float(v.dot(eu))

        def cut(s0):  # C's part up to a crease s0 along the arm
            return clip_halfplane(band, (-du.x, -du.y), -(du.x * PRu.x + du.y * PRu.y) - s0)

        def crease_len(s0):
            on = [sb(q)[1] for q in cut(s0) if abs(sb(q)[0] - s0) < 1e-6]
            return max(on) - min(on) if len(on) >= 2 else 0.0

        ss = [sb(q)[0] for q in band]
        if len(band) < 3 or max(ss) - min(ss) < 1.0:
            self.warn(f"{lab}: the arm points back over the hinge, off its triangle C; "
                      f"turn it out")
            band = tri
            ss = [sb(q)[0] for q in band]
        # the crease across the arm: where it crosses most of C, as far out as
        # that goes (straight out of C's edge beside the pivot: along that edge)
        lo, hi = min(ss), max(ss)
        cands = [hi - (hi - lo) * k / 48.0 for k in range(48)]
        s0 = max(cands, key=lambda x: (round(crease_len(x), 1), x))
        glue = cut(s0)
        P0 = PRu + s0 * du
        on = sorted({round(sb(q)[1], 6) for q in glue if abs(sb(q)[0] - s0) < 1e-6})
        pts = [P0 + b_ * eu for b_ in on if 1e-6 < b_ < wa - 1e-6]
        outer = [P0] + pts + [P0 + wa * eu, P0 + wa * eu + La * du, P0 + La * du]
        outer = [q.to_2d()[:] for q in outer]
        # as the card shuts the arm turns a right angle (anticlockwise, as
        # worked here) about the pivot: does it reach back over the fold?
        reach = min(x0 + PRu.x + math.cos(a_) * (q[0] - PRu.x) - math.sin(a_) * (q[1] - PRu.y)
                    for q in outer for a_ in (math.radians(k * 7.5) for k in range(13)))
        if reach < 1.0:
            self.warn(f"{lab}: the arm swings back over the fold as the card shuts "
                      f"(shorten it, or move the pivot out from the fold)")
        glue_p, outer_p = p_(glue), p_(outer)
        if flip:  # (mirrored: the other way round)
            glue_p, outer_p = glue_p[::-1], outer_p[::-1]
        PRm = q_(P0)  # (a point on the crease)
        dm, em = q_(du) - q_(Vector()), q_(eu) - q_(Vector())  # (directions, as drawn)
        cm = em.cross(dm)
        z0 = Matrix.Translation((0.0, 0.0, TAB_LIFT))

        def asm_arm(t):
            return Fb(t) @ mats["UR"](t) @ z0

        mid = PRm + 0.5 * wa * em
        tip = [PRm + La * dm, PRm + wa * em + La * dm]

        def asm_out(t):
            # turned on its crease so that it slopes down from there to lie
            # on the page at its tip (as it does pressed under the mask, and
            # between the pages as the card closes)
            Mu = mats["UR"](t) @ z0
            M3 = Mu.to_3x3()
            dN, cN = (M3 @ dm).z, (M3 @ cm).z
            R = math.hypot(dN, cN)
            phi = math.atan2(cN, dN)

            def turn(h):  # (the turn putting the tip's middle h above the page)
                k = (h - (Mu @ mid).z) / La
                a_ = math.acos(max(-1.0, min(1.0, k / R))) if R > 1e-9 else 0.0
                return min(((x + math.pi) % (2.0 * math.pi) - math.pi
                            for x in (phi + a_, phi - a_)), key=abs)

            def tips(b):
                Mo = Mu @ Matrix.Translation(PRm) @ Matrix.Rotation(b, 4, em) @ \
                    Matrix.Translation(-PRm)
                return [(Mo @ q).z for q in tip]

            h = TAB_LIFT
            b = turn(h)
            for _ in range(2):  # (tilted across too: its lower tip corner on the page)
                z = tips(b)
                h = TAB_LIFT + 0.5 * (z[0] + z[1]) - min(z)
                b = turn(h)
            return asm_arm(t) @ Matrix.Translation(PRm) @ Matrix.Rotation(b, 4, em) @ \
                Matrix.Translation(-PRm)

        arm = self.add(Panel(f"{ap}.End", ap, "panel", [glue_p], asm_arm,
                             f"{piece}.UR", None, f"{lab}: arm's glued end"))
        arm.free = True
        arm2 = self.add(Panel(f"{ap}.Arm", ap, "panel", [outer_p], asm_out,
                              arm.name, None, f"{lab}: arm"))
        arm2.free = True
        # does the arm run into the hinge as it swings? (shut, the hinge's
        # facets and the arm's end lie stacked, a paper's thickness apart)
        def world(pn, t):
            p = self.panels[pn]
            A = p.asm(t)
            P = [A @ Vector((q[0], q[1], 0.0)) for q in p.polys[0]]
            return P if len(P) == 3 or pn.endswith(".Arm") else P[:3]

        hits = [t for t in (40.0 + 10.0 * k for k in range(14))
                if any(_crosses(world(a_, t), world(f"{piece}.{f_}", t))
                       for a_ in (arm.name, arm2.name) for f_ in ("LR", "UL", "LL"))]
        if hits:
            self.warn(f"{lab}: the arm runs into its hinge from about {min(hits):.0f} to "
                      f"{max(hits):.0f} degrees; point it more straight out (Arm Points "
                      f"nearer 0)")
        # the mask's fold B: a host, like a box fold's corner (seen from the
        # page tab B is on, with the mask as the other page)
        if on_left:
            hB = Host(self, mask.name, 0.0, 0.0, other, 0.0, 0.0, f"{lab}: mask's fold",
                      Matrix.Translation((0.0, -q0, -Lc)) @ Matrix.Rotation(math.pi, 4, "Z"),
                      host.T2 @ Matrix.Translation((g, 0.0, 0.0)))
        else:
            hB = Host(self, other, 0.0, 0.0, mask.name, 0.0, 0.0, f"{lab}: mask's fold",
                      host.T1 @ Matrix.Translation((-g, 0.0, 0.0)),
                      Matrix.Translation((0.0, -q0, -Lc)))
        hB.finish()
        hB.trig = False
        hB.key = (uid, "B")
        hB.size = (Wm, Hm)
        self.hosts[(uid, "B")] = hB
        self.stack_ok.add(frozenset((f"{lab} hinge", f"{lab} arm")))
        self.stack_ok.add(frozenset((f"{lab} hinge", f"{lab} mask")))
        self.stack_ok.add(frozenset((lab, f"{lab} mask")))
