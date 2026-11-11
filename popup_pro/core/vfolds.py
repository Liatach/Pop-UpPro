"""V joints (two halves meeting on a crease) and the V-fold family built on
them: plain and asymmetric V-folds, arches, V-folds on top, fans, the hosts
along a V-fold's glue lines, and the mouth."""
import math

from mathutils import Matrix, Vector

from .base import (halfplanes, Hinge, Host, Panel, Piece, poly_area, split_convex, T_MIN,
                   TAB_LIFT, unit2)
from .geom import Z, ccw, clean, clip_halfplane, frame, hinge_frame_2d, v3


class VFolds:
    """V joint and V-fold builders. Mixed into Model (model.py)."""

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
        if sgn is None and J.get("rise"):
            # a 45 degree fold's crease either lies along its host's fold (the
            # paper flat on the host) or rises off it: take the one that rises
            base, k, n, nl, nr, *_ = self._crease_parts(J, self.t_ref)
            Yh = J["host"].dirs(self.t_ref)[3]
            sgn = min((1.0, -1.0), key=lambda s: abs((base + s * k * n).normalized().dot(Yh)))
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
        if m.get("on_top"):
            # at the very top of the lifting piece's crease
            lift = next((x for x in self.mechs if x["uid"] == m.get("host")), None)
            if lift is not None and lift.get("type") == "VFOLD":
                yP = float(lift["height"])
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
        self.add_piece(Piece(piece, lab, m["slot"] if "slot" in m else 1 + uid, (0.0, 0.3 * 297.0)))
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
        if shape == "FAN":
            self._fan(m, host, base, piece, lab, yP, uLf, Lc, t_)
            return
        if shape == "ZIGZAG":
            self._zigzag(m, host)
            return
        if shape in ("TRI", "BEAK_L"):
            halfL = [(0, 0), Q, GL]
        else:
            halfL = [(0, 0), Q, (GL[0], GL[1] + Lc), GL]
        if shape in ("TRI", "BEAK_R"):
            halfR = [(0, 0), GR, Q]
        else:
            halfR = [(0, 0), GR, (GR[0], GR[1] + Lc), Q]
        if shape == "M":
            # Birmingham 28-29: each half stops at a bend in its glue line,
            # where a crease (D) and crease H fan out; the half is the part
            # inside crease D
            Lh = float(m.get("m_outer_h", 40.0))
            mg = self._mgeom(m)
            halves_m = {}
            for sd, up in (("L", uLp), ("R", uRp)):
                P_, k2, _, _ = mg(up, gs[sd])
                T1_ = P_ + k2 * Lh
                halves_m[sd] = [[(0.0, 0.0), P_[:], T1_[:]], [(0.0, 0.0), T1_[:], (0.0, Lc)]]
            halfL, halfR = halves_m["L"], halves_m["R"]
        b_ = float(m.get("top_below", 0.0) or 0.0) if m.get("on_top") else 0.0
        if b_ > 0:
            # Birmingham 21: the top piece carries on below the join, down its
            # crease (D) past the lifting piece's point
            halfL = [(0.0, -b_), Q] + [p_ for p_ in halfL[2:-1]] + [GL, (GL[0], GL[1] - b_)] \
                if shape not in ("TRI", "BEAK_L") else [(0.0, -b_), Q, GL, (GL[0], GL[1] - b_)]
            halfR = [(0.0, -b_), (GR[0], GR[1] - b_), GR] + \
                ([(GR[0], GR[1] + Lc)] if shape not in ("TRI", "BEAK_R") else []) + [Q]
        FcL = hinge_frame_2d((0, 0), uLp)
        FcR = hinge_frame_2d((0, 0), uRp)
        # glued away from the spine (Birmingham 18-20): the glue lines still
        # meet at the fold, the tabs start further out along them, and the
        # piece is cut away in an arch between them
        off = {"L": float(m.get("glue_from", 0.0) or 0.0),
               "R": float(m.get("glue_from_r", m.get("glue_from", 0.0)) or 0.0)}
        for sd in ("L", "R"):
            if off[sd] > gs[sd] - 3.0:
                off[sd] = max(0.0, gs[sd] - 3.0)
                self.warn(f"{lab}: tabs start past the end of their glue line; shortened")
        halves = {"L": halfL if shape == "M" else [halfL],
                  "R": halfR if shape == "M" else [halfR]}
        if off["L"] > 0 or off["R"] > 0:
            ah = float(m.get("arch", 0.0) or 0.0) or max(off["L"], off["R"])
            ah = min(ah, Lc - 3.0)
            how = m.get("arch_shape", "STRAIGHT")
            for sd, up in (("L", uLp), ("R", uRp)):
                c0 = off[sd]
                if c0 <= 0:
                    continue
                halves[sd] = self._arch_cut(halves[sd][0], ah, c0, up, how)
        halfL, halfR = halves["L"], halves["R"]

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
            c0 = off[side]
            ins = min(0.5 * t_, 0.3 * (gs[side] - c0))
            if c0 > 0:  # glued away from the spine: the tab starts c0 out
                cp = (c0 * up[0], c0 * up[1])
                poly = [cp, gp,
                        (gp[0] + t_ * s2.x - ins * up[0], gp[1] + t_ * s2.y - ins * up[1]),
                        (cp[0] + t_ * s2.x + ins * up[0], cp[1] + t_ * s2.y + ins * up[1])]
            else:
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

        self._half(f"{base}.HalfL", piece, halfL, (0, 0), uLp, (0, 1), "L", base,
                   f"{lab}: left half")
        self._half(f"{base}.HalfR", piece, halfR, (0, 0), uRp, (0, 1), "R", base,
                   f"{lab}: right half")
        self.match_lift(f"{base}.HalfL", f"{base}.HalfR")
        on_top = bool(m.get("on_top"))
        for side, poly, T, _ in tabs:
            parent, Tp = (host.p1, host.T1) if side == "L" else (host.p2, host.T2)
            pa = self.panels[parent].asm
            Tpat = Tp @ T
            up = uLp if side == "L" else uRp
            if on_top and self._top_tabs(m, base, side, parent, Tpat, up, gs[side], t_):
                continue
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
        if shape == "M":
            self._mfold_outer(m, host, base, piece, lab, yP, (uLf, uRf), (uLp, uRp), gs, Lc, t_)

        tears = [s for s in self.samples if not self.crease(base, s)[3]]
        if tears:
            self.warn(f"{lab}: tears if opened past {min(tears):.0f} degrees (pointing "
                      f"forward, make each piece angle at least its glue angle; or turn on "
                      f"Fold Flat)")

    @staticmethod
    def _arch_cut(half, ah, c0, up, how):
        """A V-fold half with the arch between its tab start (c0 out along the
        glue line, direction up) and the crease (ah up it) cut away: convex
        pieces."""
        A = Vector((c0 * up[0], c0 * up[1]))
        B = Vector((0.0, ah))
        if how == "STRAIGHT":
            n = Vector((-(B - A).y, (B - A).x))
            if n.dot(-B) > 0:  # (pointing away from the V point)
                n = -n
            cut = clip_halfplane(half, (n.x, n.y), n.dot(B))
            return [cut] if len(cut) >= 3 else []
        e_c, e_g = Vector((0.0, ah)), Vector((c0 * up[0], c0 * up[1]))
        pts = []
        N = 16
        for i in range(N + 1):
            s_ = 0.5 * math.pi * i / N
            if how == "POINTED":
                # a gothic arch: rising from the tab start, curving in to a
                # point on the crease
                u_ = i / N
                K = A + 0.75 * e_c
                p = (1 - u_) ** 2 * A + 2 * (1 - u_) * u_ * K + u_ * u_ * B
            else:
                k = 1.0 if how == "ROUND" else 0.2  # SQUARE
                c, sn = max(0.0, math.cos(s_)), max(0.0, math.sin(s_))
                p = e_g * (c ** k) + e_c * (sn ** k)
            pts.append(p)
        region = [(0.0, 0.0)] + [q[:] for q in pts]
        region = clean(ccw(region))
        if len(region) < 3:
            return [half]
        outs, _ = split_convex(half, halfplanes(region))
        outs = [clean(q) for q in outs if len(q) >= 3 and abs(poly_area(q)) > 0.5]
        return [q for q in outs if len(q) >= 3] or [half]

    @staticmethod
    def _hull(pts):
        """Convex hull, anticlockwise."""
        pts = sorted(set((round(x, 7), round(y, 7)) for x, y in pts))
        if len(pts) < 3:
            return pts

        def cr(o, a, b):
            return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
        lo, hi = [], []
        for q in pts:
            while len(lo) >= 2 and cr(lo[-2], lo[-1], q) <= 1e-12:
                lo.pop()
            lo.append(q)
        for q in reversed(pts):
            while len(hi) >= 2 and cr(hi[-2], hi[-1], q) <= 1e-12:
                hi.pop()
            hi.append(q)
        return lo[:-1] + hi[:-1]

    def _top_tabs(self, m, base, side, parent, Tpat, up, g, depth):
        """A V-fold on top of a V-fold (Birmingham 21-22): the lifting piece's
        top is cut to a point along the glue lines, and its own tabs (A) fold
        over them and stick under the top piece. False: not on a V-fold's
        half, so the top piece keeps its usual tabs."""
        import re
        lab = m["label"]
        if not re.fullmatch(r"VFold\d+\.Half[LR]", parent):
            if side == "L":
                self.warn(f"{lab}: On Top stands on a V-fold's crease; usual tabs")
            return False
        P = self.panels[parent]
        # the glue line, in the lifting piece's pattern
        a0 = (Tpat @ Vector((0.0, 0.0, 0.0))).to_2d()
        a1 = (Tpat @ Vector((g * up[0], g * up[1], 0.0))).to_2d()
        u = (a1 - a0).normalized()
        n = Vector((-u.y, u.x))
        V = Vector((0.0, 0.0))  # the lifting piece's V point
        if n.dot(V - a0) > 0:
            n = -n  # (pointing out, away from the lifting piece)
        cx = sum(q[0] for poly in P.polys for q in poly)
        sx = 1.0 if cx > 0 else -1.0
        if u.y > 0.02 and u.x * sx > 0 and P.polys:
            # Birmingham 22: the lines rise from the crease's top, so the top
            # is a V. The half's outer side grows up to meet its line
            xo = max(abs(q[0]) for poly in P.polys for q in poly)
            Pe = a0 + u * (abs(xo - abs(a0.x)) / max(abs(u.x), 1e-9))
            k = max(range(len(P.polys)), key=lambda i: max(
                (abs(q[0]), q[1]) for q in P.polys[i]))
            P.polys[k] = self._hull(list(P.polys[k]) + [Pe[:]])
        # how far along the line the lifting piece reaches
        reach = 0.0
        for poly in P.polys:
            for i in range(len(poly)):
                p_, q_ = Vector(poly[i]), Vector(poly[(i + 1) % len(poly)])
                d = q_ - p_
                den = u.x * d.y - u.y * d.x
                if abs(den) < 1e-9:
                    continue
                w = p_ - a0
                s_ = (w.x * d.y - w.y * d.x) / den
                r_ = (w.x * u.y - w.y * u.x) / den
                if -1e-6 <= r_ <= 1.0 + 1e-6:
                    reach = max(reach, s_)
        if reach < 3.0:
            self.warn(f"{lab}: the glue lines miss the lifting piece; usual tabs")
            return False
        # the lifting piece's top, cut to the glue lines
        cuts = [clip_halfplane(q, (-n.x, -n.y), -n.dot(a0)) for q in P.polys]
        def dedupe(q):
            out = []
            for p_ in q:
                if not out or (abs(p_[0] - out[-1][0]) + abs(p_[1] - out[-1][1])) > 1e-4:
                    out.append(p_)
            while len(out) > 1 and abs(out[0][0] - out[-1][0]) + abs(out[0][1] - out[-1][1]) \
                    <= 1e-4:
                out.pop()
            return out
        cuts = [clean(ccw(dedupe(q))) for q in cuts if len(q) >= 3 and abs(poly_area(q)) > 1e-6]
        cuts = [q for q in cuts if len(q) >= 3]
        if not cuts:
            return False
        P.polys = cuts
        L = min(g, reach)
        b1 = a0 + u * L
        ins = min(0.5 * depth, 0.3 * L)
        tab = [a0[:], b1[:], (b1 + n * depth - u * ins)[:], (a0 + n * depth + u * ins)[:]]
        # keep clear of the lifting piece's own crease (x = 0 in its pattern)
        sg = 1.0 if cx > 0 else -1.0
        tab = clip_halfplane(tab, (sg, 0.0), 0.4)
        half = self.panels[f"{base}.Half{side}"]
        # and on the top piece: inside its half
        for hp in half.polys[:1]:
            over = ccw([(Tpat @ v3(q)).to_2d()[:] for q in hp])
            for nn, dd in halfplanes(over):
                tab = clip_halfplane(tab, nn, dd + 0.3 * math.hypot(*nn))
        tab = clean(tab) if len(tab) >= 3 else tab
        if len(tab) < 3 or abs(poly_area(tab)) < 1.0:
            return False
        Ti = Tpat.inverted()
        self.add(Panel(f"{base}.TopTab{side}", P.piece, "tab", [tab],
                       (lambda t, ha=half.asm, T=Ti: ha(t) @ T), half.name, None,
                       f"{lab}: tab A {side} (on the lifting piece)"))
        self.top_cut.add(parent)
        return True

    def _fan(self, m, host, base, piece, lab, yP, uLf, R_, t_):
        """A pleated fan: a row of small V-folds side by side, sharing their
        glue lines. Its paper spans Spread degrees, more than the gap between
        its two glued edges ever is, so the pleats are what make it fit: the
        valleys lie evenly across the plane of the two glue lines, each ridge
        stands out of it just far enough for its two sectors to reach. Shut,
        every sector lies flat against the next; open, it fans out, and never
        quite flat (there's more paper than room)."""
        N = max(1, int(m.get("fan_pleats", 3)))
        Phi = math.radians(float(m.get("fan_spread", 180.0)))
        d = 0.5 * Phi / N  # each sector's angle at the V point
        E = math.radians(float(m.get("fan_stand", 60.0)))  # how far the middle stands
        J = self.joints[base]
        tr = self.t_ref
        _b, _k, n0, nl0, nr0, uL0, uR0, _ok, _P = self._crease_parts(J, tr)
        want = nl0 + nr0
        if J.get("gap") and self.normals_out(host):
            want = -want
        sn = 1.0 if uL0.cross(uR0).dot(want) >= 0 else -1.0
        cache = {}
        tight = []
        # Stand: the middle's rise out of the glue lines' plane, fully open
        x0 = 0.5 * math.acos(max(-1.0, min(1.0, self._crease_parts(J, self.tmax)[5].dot(
            self._crease_parts(J, self.tmax)[6]))))
        kst = (math.acos(max(-1.0, min(1.0, math.cos(x0) * math.cos(E)))) / x0
               if x0 > 1e-6 else 1.0)

        def rays(t):
            """World directions of the 2N+1 creases from the V point, and it."""
            r = cache.get(t)
            if r is not None:
                return r
            _b, _k, _n, nl, nr, uL, uR, _ok, P3 = self._crease_parts(J, t)
            G = max(-1.0, min(1.0, uL.dot(uR)))
            Th = math.acos(G)
            cr = uL.cross(uR)
            if cr.length > 1e-9:
                n = sn * cr.normalized()
                cache["n"] = n
            else:  # shut flat: the side it stood out to a moment before
                n = cache.get("n", nl.normalized())
            # the middle stands out of the glue lines' plane (Stand), more the
            # further the card opens: valleys follow one glue line up over it
            # and down to the other, evenly; shut, it lies down with the rest
            w = uR - G * uL  # across the glue lines' plane, towards the other one
            w = w.normalized() if w.length > 1e-9 else n.cross(uL).normalized()
            mid = (math.cos(0.5 * Th) * uL + math.sin(0.5 * Th) * w).normalized()
            # the middle is the crease of a V-fold whose piece angle is k times
            # half the gap between the glue lines: it always stays in the gap
            # between the pages, and lies down as they close (Stand sets k)
            x = 0.5 * Th
            # eased: near shut the pleats collapse first (as a hand fan closes)
            # and only then does the middle lie down with them
            f = max(0.0, min(1.0, t / max(1.0, self.tmax))) ** 2
            k = 1.0 + (kst - 1.0) * f
            ce = math.cos(min(math.pi, k * x)) / max(1e-9, math.cos(x))
            e = math.acos(max(-1.0, min(1.0, ce)))
            c = (math.cos(e) * mid + math.sin(e) * n).normalized()
            A1 = math.acos(max(-1.0, min(1.0, uL.dot(c))))
            A2 = math.acos(max(-1.0, min(1.0, c.dot(uR))))
            Ltot = A1 + A2

            def along(sv):
                """The point sv of the way (radians) along the valleys' path."""
                a, b, ang, s0 = (uL, c, A1, sv) if sv <= A1 else (c, uR, A2, sv - A1)
                if ang < 1e-9:
                    return a.copy()
                f = s0 / ang
                return ((math.sin((1 - f) * ang) * a + math.sin(f * ang) * b) /
                        math.sin(ang)).normalized()

            vs = [along(Ltot * i / N) for i in range(N + 1)]
            out = []
            for i in range(N + 1):
                out.append(vs[i])
                if i == N:
                    break
                a, b = vs[i], vs[i + 1]
                beta = math.acos(max(-1.0, min(1.0, a.dot(b))))
                ch = math.cos(d) / max(1e-9, math.cos(0.5 * beta))
                if ch > 1.0 + 1e-9:
                    tight.append(t)
                ch = min(1.0, ch)
                sh = math.sqrt(max(0.0, 1.0 - ch * ch))
                mm = a + b
                mm = mm.normalized() if mm.length > 1e-9 else a.copy()
                nn = a.cross(b)
                if nn.length < 1e-9:
                    nn = n.copy()  # shut: they lift the way the fan opens
                nn.normalize()
                if nn.dot(n) < 0:
                    nn = -nn  # ridges stand out on the same side as the middle
                out.append((ch * mm + sh * nn).normalized())
            r = (out, P3)
            if len(cache) > 4000:
                cache.clear()
            cache[t] = r
            return r

        a0 = 0.5 * math.pi + 0.5 * Phi
        pat = [(math.cos(a0 - k * d), math.sin(a0 - k * d)) for k in range(2 * N + 1)]

        def basis(a, b):
            e1 = Vector(a).normalized()
            e2 = (Vector(b) - e1 * e1.dot(Vector(b))).normalized()
            return Matrix((e1, e2, e1.cross(e2))).transposed()

        def make(k, mx):
            pa = Vector((mx * pat[k][0], pat[k][1], 0.0))
            pb = Vector((mx * pat[k + 1][0], pat[k + 1][1], 0.0))
            F = basis(pa, pb)

            def asm(t, k=k, F=F):
                W, P3 = rays(t)
                Rm = basis(W[k], W[k + 1]) @ F.transposed()
                M = Rm.to_4x4()
                M.translation = P3
                return M
            return asm

        # the printed side faces into the card (as a V-fold's does)
        mx = 1.0
        if (make(0, 1.0)(self.tmax).to_3x3() @ Vector((0, 0, 1))).dot(
                self._crease_parts(J, self.tmax)[3]) < 0:
            mx = -1.0
        seg = max(2, int(math.ceil(24 / (2 * N))))
        prev = host.p1
        names = []
        # glued away from the spine: the fan's hub is cut away and its tabs
        # start that far out along the end edges
        offL = min(float(m.get("glue_from", 0.0) or 0.0), R_ - 3.0)
        offR = min(float(m.get("glue_from_r", m.get("glue_from", 0.0)) or 0.0), R_ - 3.0)

        def hub(k):
            return offL + (offR - offL) * k / (2 * N)
        for k in range(2 * N):
            poly = [(0.0, 0.0)]
            for j in range(seg + 1):
                a = a0 - (k + j / seg) * d
                poly.append((mx * R_ * math.cos(a), R_ * math.sin(a)))
            if hub(k) > 0 or hub(k + 1) > 0:
                A_ = Vector((mx * pat[k][0], pat[k][1])) * hub(k)
                B_ = Vector((mx * pat[k + 1][0], pat[k + 1][1])) * hub(k + 1)
                nn = Vector((-(B_ - A_).y, (B_ - A_).x))
                if nn.dot(-A_ - B_) > 0:
                    nn = -nn  # (away from the hub)
                poly = clip_halfplane(poly, (nn.x, nn.y), nn.dot(A_))
            name = f"{base}.Fan{k + 1}"
            asm = make(k, mx)
            Fc = hinge_frame_2d((0.0, 0.0), (mx * pat[k][0], pat[k][1]))
            Hp = self.panels[prev].asm(tr).inverted() @ asm(tr) @ Fc
            hg = Hinge(Hp, Fc, "TABLE")
            hg.corner_ok = True
            hg.host_bound = True
            kind = "ridge" if k % 2 else "valley"
            self.add(Panel(name, piece, "panel", [poly], asm, prev, hg,
                           f"{lab}: pleat {k // 2 + 1} {'right' if k % 2 else 'left'}"))
            names.append(name)
            prev = name
        # glue tabs along the two end edges, flat on their pages
        inside = m.get("tab_side", "IN") == "IN"
        for side, ke, page, k_in in (("L", 0, host.p1, 1), ("R", 2 * N, host.p2, 2 * N - 1)):
            p = Vector((mx * pat[ke][0], pat[ke][1], 0.0))
            pin = Vector((mx * pat[k_in][0], pat[k_in][1], 0.0))
            s2 = Vector((p.y, -p.x, 0.0))
            if s2.dot(pin) > 0:
                s2 = -s2  # away from the fan
            c0 = offL if side == "L" else offR
            ins = min(0.5 * t_, 0.3 * (R_ - c0))
            poly = [(c0 * p.x, c0 * p.y), (R_ * p.x, R_ * p.y),
                    (R_ * p.x + t_ * s2.x - ins * p.x, R_ * p.y + t_ * s2.y - ins * p.y),
                    (c0 * p.x + t_ * s2.x + (ins if c0 > 0 else 0) * p.x,
                     c0 * p.y + t_ * s2.y + (ins if c0 > 0 else 0) * p.y)]
            W, P3 = rays(tr)
            u = W[ke]
            other = W[2 * N] if side == "L" else W[0]
            npage = self.panels[page].asm(tr).to_3x3() @ Vector((0, 0, 1))
            q = u.cross(npage).normalized()
            if (q.dot(other) > 0) != inside:
                q = -q
            lift = host.lift[0 if side == "L" else 1]
            Wt = frame(P3 + lift * TAB_LIFT * npage, q, u) @ frame((0, 0, 0), s2, p).inverted()
            Tc = self.panels[page].asm(tr).inverted() @ Wt
            # stay on this side of the fold it stands on, as a V-fold's tabs do
            Tv = (host.T1 if side == "L" else host.T2).inverted() @ Tc
            sgn = -1.0 if side == "L" else 1.0
            poly = clip_halfplane(poly, (sgn * Tv[0][0], sgn * Tv[0][1]), 0.5 - sgn * Tv[0][3])
            pa_ = self.panels[page].asm
            self.add(Panel(f"{base}.Tab{side}", piece, "tab", [poly],
                           (lambda t, pa=pa_, T=Tc: pa(t) @ T), page, None, f"{lab}: tab {side}"))
        if m.get("lines"):
            self.warn(f"{lab}: a fan makes its own creases; extra lines are left out")
        rays(self.tmax)
        if tight:
            self.warn(f"{lab}: not enough Spread for the gap it bridges (it would tear "
                      f"opened past about {min(tight):.0f} degrees): widen Spread or "
                      f"narrow the glue angles")

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
        if uf is None:
            return  # (an M-fold's halves aren't glued: only its crease)
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
            self.match_lift(f"{key}L", f"{key}R")
            self.cut_panels |= {f"{key}L", f"{key}R"}
