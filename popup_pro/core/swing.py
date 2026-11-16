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

from .base import Panel, Piece, TAB_LIFT
from .geom import frame


def _tri(P, W):
    """The rigid map taking pattern triangle P (2D) onto world triangle W."""
    p = [Vector((q[0], q[1], 0.0)) for q in P]
    return frame(W[0], W[1] - W[0], W[2] - W[0]) @ frame(p[0], p[1] - p[0],
                                                       p[2] - p[0]).inverted()


def _hull(pts):
    """Convex hull, anticlockwise (monotone chain)."""
    pts = sorted(set((round(x, 6), round(y, 6)) for x, y in pts))
    if len(pts) < 3:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, hi = [], []
    for p in pts:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 0:
            lo.pop()
        lo.append(p)
    for p in reversed(pts):
        while len(hi) >= 2 and cross(hi[-2], hi[-1], p) <= 0:
            hi.pop()
        hi.append(p)
    return lo[:-1] + hi[:-1]


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
            return 2.0 * TAB_LIFT * max(0.0, -c)

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
            return frame(S + g * od + q0 * Yb + (lift(od.dot(rb)) + 2.0 * TAB_LIFT) * nb,
                         rb, Yb)

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
        # the arm: its glue end the triangle C, then out at its angle (open
        # flat; + anticlockwise as seen)
        ang = math.radians(float(m.get("swing_angle", 0.0) or 0.0))
        ap = f"SwArm{uid}"
        self.add_piece(Piece(ap, f"{lab} arm", 1 + uid, (g, -0.5 * La)))
        tri = p_([(g + 0.5, 1.5), (2.0 * g - 1.5, g - 0.5), (g + 0.5, g - 0.5)])
        cx, cy = sum(q[0] for q in tri) / 3.0, sum(q[1] for q in tri) / 3.0
        # (0: straight out of the hinge, away from its pivot, tab D's corner;
        # the pattern runs as the view, or turned half round: anticlockwise alike)
        dx, dy = math.sin(ang), -math.cos(ang)
        if flip:
            dx, dy = -dx, -dy
        nx, ny = -dy, dx
        strip = [(cx + a * dx + b * nx, cy + a * dy + b * ny)
                 for a, b in ((0.0, -0.5 * wa), (La, -0.5 * wa), (La, 0.5 * wa),
                              (0.0, 0.5 * wa))]
        arm_poly = _hull(tri + strip)

        PRm = Vector((2.0 * g, g if not flip else 0.0, 0.0))  # (the pivot, as drawn)

        def asm_arm(t):
            # its glued end turns with C, which tilts up as the hinge folds;
            # the arm itself, pressed between the page and the mask, stays
            # flat between them, turning as C turns round the pivot
            V, T, PR, PL, E, off = solve(t)
            d = q_(T) - q_(PR)
            phi = math.atan2(d.y, d.x) - math.pi  # (C's top edge runs -x, drawn)
            z = 0.5 * off.z + TAB_LIFT
            return Fb(t) @ Matrix.Translation(PRm + Vector((0.0, 0.0, z))) @ \
                Matrix.Rotation(phi, 4, "Z") @ Matrix.Translation(-PRm)

        arm = self.add(Panel(f"{ap}.Arm", ap, "panel", [arm_poly], asm_arm,
                             f"{piece}.UR", None, f"{lab}: arm"))
        arm.free = True
        self.stack_ok.add(frozenset((f"{lab} hinge", f"{lab} arm")))
        self.stack_ok.add(frozenset((f"{lab} hinge", f"{lab} mask")))
        self.stack_ok.add(frozenset((lab, f"{lab} mask")))
