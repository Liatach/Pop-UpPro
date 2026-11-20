"""Tubes on parallel sticking strips: boxes, hexagons, cylinders, loops and
cones, the walls' frames and plans, and the corner and crease folds that
towers stand in."""
import math

from mathutils import Matrix, Vector

from .base import (Hinge, Host, Panel, Piece, poly_area, round_arc, ROUND_FACETS, ROUND_FMAX,
                   T_MIN, TAB_LIFT)
from .geom import Z, ccw, clip_halfplane, frame, hinge_frame_2d, v3


def _hull2(ps):
    """Convex hull of 2D points, counter-clockwise."""
    ps = sorted(set((round(p[0], 9), round(p[1], 9)) for p in ps))
    if len(ps) < 3:
        return ps

    def cr(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lo, hi = [], []
    for p in ps:
        while len(lo) >= 2 and cr(lo[-2], lo[-1], p) <= 0:
            lo.pop()
        lo.append(p)
    for p in reversed(ps):
        while len(hi) >= 2 and cr(hi[-2], hi[-1], p) <= 0:
            hi.pop()
        hi.append(p)
    return lo[:-1] + hi[:-1]


class Tubes:
    """Tube builders. Mixed into Model (model.py)."""

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
        if T.get("rf") or T.get("rb"):
            c = T.setdefault("cache", {})
            k = float(t)
            if k not in c:
                if len(c) > 4096:
                    c.clear()
                c[k] = self._tube_plan(uid, t)
            return dict(c[k])
        return self._tube_plan(uid, t)

    def _tube_plan(self, uid, t):
        T = self.tubes[uid]
        host, a, y0, D = T["host"], T["a"], T["y0"], T["D"]
        S, e, xh, Y, sn, cs = self.strip_frame(host, t)
        x = a * sn
        pf = math.sqrt(max(T["wf"] ** 2 - x * x, 0.0))
        pb = math.sqrt(max(T["wb"] ** 2 - x * x, 0.0))
        out = dict(BL=(-x, y0 + D), FL=(-x, y0), FR=(x, y0), BR=(x, y0 + D),
                   CF=(0.0, y0 - T["sf"] * pf), CB=(0.0, y0 + D + T["sb"] * pb))
        if T.get("rf"):
            n = T["nf"]
            arc = round_arc(x, T["wf"], n)
            for k in range(1, n):
                dx, dy = arc[k]
                out[f"fL{k}"] = (-x + dx, y0 - dy)
                out[f"fR{k}"] = (x - dx, y0 - dy)
            out["CF"] = (-x + arc[n][0], y0 - arc[n][1])
        if T.get("rb"):
            n = T["nb"]
            arc = round_arc(x, T["wb"], n)
            for k in range(1, n):
                dx, dy = arc[k]
                out[f"bL{k}"] = (-x + dx, y0 + D + dy)
                out[f"bR{k}"] = (x - dx, y0 + D + dy)
            out["CB"] = (-x + arc[n][0], y0 + D + arc[n][1])
        return out

    def _corner_hosts(self, uid, lab, P, u, hgt, walls=None, creases=()):
        """A tube's four inside corners, where a side wall meets the front or
        back: folds a tower (a glued box fold) stands in, inside the tube.
        Seen from inside, the corner is 90 degrees with the walls square and
        opens out to 180 as the card shuts, so a box fold there lies flat
        with the tube. Virtual y runs up the corner from the page."""
        t = self.t_ref
        if walls is None:
            walls = {n: dict(u0=u[i], u1=u[i + 1])
                     for i, n in enumerate(("FL_", "GFL", "GFR", "FR_", "GBR", "GBL"))}
        mids = [P[n].asm(t) @ Vector((0.5 * (w["u0"] + w["u1"]), 0.5 * hgt, 0.0))
                for n, w in walls.items()]
        cen = sum(mids, Vector()) / len(mids)
        R = Matrix.Rotation(math.pi, 4, "Y")
        for key, wa, ua, wb, ub, txt in (
                ("KFL", "FL_", u[1], "GFL", u[1], "front left corner"),
                ("KFR", "GFR", u[3], "FR_", u[3], "front right corner"),
                ("KBR", "FR_", u[4], "GBR", u[4], "back right corner"),
                ("KBL", "GBL", u[6], "FL_", u[0], "back left corner"),
                # the front and back creases, pointing out: inside they close
                # to 0 as the card shuts, like the spine
                ("KF", "GFL", u[2], "GFR", u[2], "front crease"),
                ("KB", "GBR", u[5], "GBL", u[5], "back crease")):
            if key in ("KF", "KB") and key not in creases:
                continue
            if wa not in P or wb not in P:
                continue
            A = P[wa].asm(t)
            inside = (A.to_3x3() @ Z).dot(cen - A @ Vector((ua, 0.5 * hgt, 0.0))) > 0
            if inside:  # the walls' printed side faces in: x runs with u
                p1, T1 = P[wa].name, Matrix.Translation((ua, 0.0, 0.0))
                p2, T2 = P[wb].name, Matrix.Translation((ub, 0.0, 0.0))
            else:  # turned round, so the virtual pages' printed side is inside
                p1, T1 = P[wb].name, Matrix.Translation((ub, 0.0, 0.0)) @ R
                p2, T2 = P[wa].name, Matrix.Translation((ua, 0.0, 0.0)) @ R
            h = Host(self, p1, 0.0, 0.0, p2, 0.0, 0.0, f"{lab}: {txt}", T1, T2).finish()
            h.trig = False
            h.key = uid
            h.tower_top = hgt  # the walls' top: a tower raises them behind it
            self.hosts[(uid, key)] = h

    def _raise_walls(self, host, a, b, top):
        """A tower in a tube's corner: its two outer faces are the walls
        themselves, so they rise to the tower's top over its width."""
        was = host.tower_top
        for pn, T, lo, hi in ((host.p1, host.T1, -a, 0.0), (host.p2, host.T2, 0.0, b)):
            p = self.panels[pn]
            Ti = T.inverted()
            polys = []
            for poly in p.polys:
                V = [(Ti @ v3(q)).to_2d()[:] for q in poly]
                left = clip_halfplane(V, (-1.0, 0.0), -lo)
                mid = clip_halfplane(clip_halfplane(V, (1.0, 0.0), lo), (-1.0, 0.0), -hi)
                right = clip_halfplane(V, (1.0, 0.0), hi)
                mid = [(x, top if y > was - 1e-6 else y) for x, y in mid]
                for part in (left, mid, right):
                    if len(part) >= 3 and abs(poly_area(part)) > 1e-6:
                        polys.append([(T @ Vector((x, y, 0.0))).to_2d()[:] for x, y in part])
            p.polys = [ccw(q) for q in polys]

    def _wall_asm(self, host, a, P, Q, u0, pts_fn, frame_fn=None):
        """Wall standing along e from plan point P to Q (keys into pts_fn(t)),
        its pattern starting at u = u0."""
        Pi = frame(Vector((u0, 0, 0)), (1, 0, 0), (0, 1, 0)).inverted()
        frame_fn = frame_fn or (lambda t: self.strip_frame(host, t))

        def asm(t):
            pts = pts_fn(t)
            S, e, xh, Y, sn, cs = frame_fn(t)
            o = S + a * cs * e
            p, q = pts[P], pts[Q]
            p3 = o + p[0] * xh + p[1] * Y
            q3 = o + q[0] * xh + q[1] * Y
            return frame(p3, (q3 - p3).normalized(), e) @ Pi

        return asm

    def _cone(self, m, host, rt):
        """A round tube whose walls lean in (or out) toward the top: a slice of
        a cone, its top Top Radius across where its bottom is the strip
        distance (the loop narrowed or flared). Its side walls are glued to the
        strips like a tube's; every wall turns about the cone's point, which
        rides up and down the mirror plane as the card opens (like a pyramid's
        apex), so it folds flat. The round ends are facets whose turns between
        them grow or shrink together, keeping the crease on the mirror plane.
        Cut as one curved band (two if it wraps too far round)."""
        uid, lab = m["uid"], m["label"]
        a, y0 = float(m["x"]), float(m["y"])
        D, hb = max(2.0, float(m["depth"])), float(m["height"])
        n = ROUND_FACETS
        if hb < 2.0:
            self.warn(f"{lab}: too low to make; skipped")
            return
        H = hb * a / (a - rt)  # the cone's point above the card (below if it flares)
        ym = y0 + 0.5 * D
        f_top = hb / H  # how far along each line to the point the top is
        if rt < 1.0:
            self.warn(f"{lab}: comes to a point; made 1 mm across at the top")
        if host.is_spine and (y0 - a < -1e-6 or y0 + D + a > self.H + 1e-6):
            self.warn(f"{lab}: runs past the top or bottom of the card")
        L = math.hypot(a, H)  # side wall, foot to point
        sg = 1.0 if H > 0 else -1.0
        # open flat (the design): its bottom on the card, half circles each end
        Q0 = Vector((0.0, ym, H))
        def at180(px, py):
            return Vector((px, py, 0.0))
        ph = [0.5 * math.pi * k / n for k in range(n + 1)]
        frontL = [at180(-a * math.cos(p_), y0 - a * math.sin(p_)) for p_ in ph]  # CL .. F
        backL = [at180(-a * math.cos(p_), y0 + D + a * math.sin(p_)) for p_ in ph]  # C0L .. B
        CL0, C0L0 = frontL[0], backL[0]

        def dirs(pts, Q):
            return [(p_ - Q).normalized() for p_ in pts]

        def turns(us, u_prev):
            """Turn at each point of a chain on the sphere round the point (the
            first relative to carrying on from u_prev), and the steps."""
            out, steps = [], []
            n_ = u_prev.cross(us[0])
            T = n_.cross(us[0]).normalized()
            for k in range(len(us) - 1):
                p_, q_ = us[k], us[k + 1]
                To = (q_ - q_.dot(p_) * p_).normalized()
                tau = math.atan2(p_.dot(T.cross(To)), T.dot(To))
                al = math.acos(max(-1.0, min(1.0, p_.dot(q_))))
                out.append(tau)
                steps.append(al)
                T = (-math.sin(al) * p_ + math.cos(al) * To).normalized()
            return out, steps

        design = {}
        for key, pts, prev in (("F", frontL, C0L0), ("B", backL, CL0)):
            us = dirs(pts, Q0)
            design[key] = turns(us, (prev - Q0).normalized())
        lens = {"F": [(p_ - Q0).length for p_ in frontL],
                "B": [(p_ - Q0).length for p_ in backL]}

        def walk(u0, u_prev, taus, steps, kap):
            n_ = u_prev.cross(u0)
            T = n_.cross(u0).normalized()
            p_ = u0
            out = [u0]
            for tau, al in zip(taus, steps):
                T = (math.cos(kap * tau) * T + math.sin(kap * tau) * p_.cross(T)).normalized()
                q_ = (math.cos(al) * p_ + math.sin(al) * T).normalized()
                T = (-math.sin(al) * p_ + math.cos(al) * T).normalized()
                p_ = q_
                out.append(p_)
            return out

        cache = {}

        def geo(t):
            k_ = float(t)
            g = cache.get(k_)
            if g is not None:
                return g
            S, e, xh, Y, sn, cs = self.strip_frame(host, t)
            vq = a * cs + sg * math.sqrt(max(L * L - a * a * sn * sn, 0.0))
            Q = S + vq * e + ym * Y
            CL = S + a * cs * e - a * sn * xh + y0 * Y
            C0L = S + a * cs * e - a * sn * xh + (y0 + D) * Y
            res = {"Q": Q, "xh": xh, "S": S}
            for key, u0p, uprev in (("F", CL, C0L), ("B", C0L, CL)):
                u0 = (u0p - Q).normalized()
                up = (uprev - Q).normalized()
                taus, steps = design[key]

                def g_(kap):
                    return walk(u0, up, taus, steps, kap)[-1].dot(xh)
                k1 = k_cache.get(key, 1.0)
                # bracket the root near the last one
                lo, hi = k1 - 0.05, k1 + 0.05
                flo, fhi = g_(lo), g_(hi)
                grow = 0.1
                while flo * fhi > 0 and grow < 8.0:
                    lo, hi = lo - grow, hi + grow
                    flo, fhi = g_(lo), g_(hi)
                    grow *= 2.0
                if flo * fhi > 0:
                    kap = k1
                else:
                    for _ in range(50):
                        md = 0.5 * (lo + hi)
                        fm = g_(md)
                        if fm * flo > 0:
                            lo, flo = md, fm
                        else:
                            hi = md
                    kap = 0.5 * (lo + hi)
                    k_cache[key] = kap
                res[key] = walk(u0, up, taus, steps, kap)
            if len(cache) > 4096:
                cache.clear()
            cache[k_] = res
            return res

        k_cache = {}

        def mirror(u, xh):
            return u - 2.0 * u.dot(xh) * xh

        # the strip's lines to the point, in order round: the left side, the
        # front left and right, the right side, the back right and left
        # (key, index into the chain, mirrored)
        seq = [("B", 0, False), ("F", 0, False)] + [("F", k, False) for k in range(1, n + 1)] + \
            [("F", k, True) for k in range(n - 1, -1, -1)] + [("B", 0, True)] + \
            [("B", k, True) for k in range(1, n + 1)] + [("B", k, False) for k in range(n - 1, -1, -1)]

        def u_of(g, node):
            key, k, mir = node
            u = g[key][k]
            return mirror(u, g["xh"]) if mir else u

        def len_of(node):
            return lens[node[0]][node[1]]

        # unrolled about the point: each line's angle round from the last
        g180 = geo(180.0)
        U = [u_of(g180, nd) for nd in seq]
        th0 = [0.0]
        for i in range(1, len(U)):
            th0.append(th0[-1] + math.acos(max(-1.0, min(1.0, U[i - 1].dot(U[i])))))
        two = th0[-1] > math.radians(300.0)
        i_split = 2 * n + 2  # (the back starts at the right side's back line)
        piece = f"Tube{uid}"
        pB = f"{piece}b" if two else piece
        self.add_piece(Piece(piece, lab if not two else f"{lab} (front)", 1 + uid,
                             (0.0, 0.0)))
        if two:
            self.add_piece(Piece(pB, f"{lab} (back)", 350 + uid, (0.0, 0.0)))
        self.tubes[uid] = dict(host=host, a=a, y0=y0, D=D, wf=0.5 * math.pi * a,
                               wb=0.5 * math.pi * a, sf=1.0, sb=1.0, h=hb, label=lab,
                               rf=True, rb=True, nf=n, nb=n, cone=True, walls={})
        flip = [1.0]

        face = bool(m.get("face"))
        i_cb = 3 * n + 2  # (the back's centre line)
        cut_cb = face and not two

        def ang(i, pnl):
            """Line i's angle in panel pnl's pattern (the back's own strip
            starts again at 0 when it's cut separately; a face's band is cut
            at the back's centre, so the back left wraps round before the
            left side)."""
            if cut_cb and pnl >= i_cb:
                return flip[0] * (th0[i] - th0[-1])
            sh = th0[i_split] if (two and pnl >= i_split) else 0.0
            return flip[0] * (th0[i] - sh)

        def pt2(i, frac, pnl):
            r_ = len_of(seq[i]) * frac
            th_ = ang(i, pnl)
            return (r_ * math.sin(th_), -r_ * math.cos(th_))

        def d2(i, pnl):
            th_ = ang(i, pnl)
            return Vector((math.sin(th_), -math.cos(th_), 0.0))

        def onward(i, pnl):  # across line i, toward line i+1 in panel pnl's pattern
            th_ = ang(i, pnl)
            return Vector((math.cos(th_), math.sin(th_))) * flip[0]

        def make_asm(i):
            Fp = frame(Vector((0.0, 0.0, 0.0)), d2(i, i), d2(i + 1, i)).inverted()

            def asm(t, i=i, Fp=Fp):
                g = geo(t)
                return frame(g["Q"], u_of(g, seq[i]), u_of(g, seq[i + 1])) @ Fp
            return asm

        def quad(i):
            return [pt2(i, 1.0, i), pt2(i + 1, 1.0, i), pt2(i + 1, 1.0 - f_top, i),
                    pt2(i, 1.0 - f_top, i)]

        # printed side out: the left side's printed face toward -xh
        nrm = make_asm(0)(120.0).to_3x3() @ Vector((0.0, 0.0, 1.0))
        if nrm.dot(geo(120.0)["xh"]) > 0:
            flip[0] = -1.0

        names = []
        for i in range(len(seq) - 1):
            if i == 0:
                nm, grp, lb = "FL_", "FL_", "left side"
            elif i <= n:
                nm, grp, lb = f"GFL{i}", "GFL", f"front left {i}"
            elif i <= 2 * n:
                nm, grp, lb = f"GFR{i - n}", "GFR", f"front right {i - n}"
            elif i == 2 * n + 1:
                nm, grp, lb = "FR_", "FR_", "right side"
            elif i <= 3 * n + 1:
                nm, grp, lb = f"GBR{i - 2 * n - 1}", "GBR", f"back right {i - 2 * n - 1}"
            else:
                nm, grp, lb = f"GBL{i - 3 * n - 1}", "GBL", f"back left {i - 3 * n - 1}"
            names.append((nm, grp, lb))
        P = {}
        for i, (nm, grp, lb) in enumerate(names):
            pc_ = pB if (two and i >= i_split) else piece
            asm = make_asm(i)
            poly = ccw(quad(i))
            if nm in ("FL_", "FR_"):
                par = host.p1 if nm == "FL_" else host.p2
                hg = self._hinge_on(par, asm, pt2(i, 1.0, i), pt2(i + 1, 1.0, i))
            else:
                par = P[names[i - 1][0]].name
                hg = self._hinge_on(par, asm, pt2(i, 1.0, i), pt2(i, 1.0 - f_top, i))
            P[nm] = self.add(Panel(f"{piece}.{nm}", pc_, "panel", [poly], asm, par, hg,
                                   f"{lab}: {lb}"))
            if P[nm] is None:
                self.warn(f"{lab}: too small to make")
                return
            P[nm].hinge.kink_ok = True
            if i > 0 and names[i - 1][1] == grp and nm != grp:
                pair = frozenset((P[names[i - 1][0]].name, P[nm].name))
                self.fold_kind[pair] = "skip"
                self.facets.add(pair)
            if nm.startswith("G"):
                self.smooth_panels.add(P[nm].name)
        tb = float(m.get("tab", 10.0))
        ch = min(0.3 * tb, 0.2 * abs(hb))
        tbc = min(tb, 0.9 * D * min(1.0, 1.0 - f_top))  # (the side wall's narrow end)

        def end_tab(name, src_i, line, beyond, target, into, pc_, wide=None):
            """A tab off panel src_i's edge on line (toward beyond, in its
            pattern), glued inside target (into: across the shared edge, into
            the target, in its pattern)."""
            e0, e1 = pt2(line, 1.0, src_i), pt2(line, 1.0 - f_top, src_i)
            ev = (Vector(e1) - Vector(e0)).normalized()
            tw = tbc if wide is None else min(tbc, wide)
            poly = [e0, e1, tuple(Vector(e1) + tw * beyond - ch * ev),
                    tuple(Vector(e0) + tw * beyond + ch * ev)]
            self.add(Panel(f"{piece}.{name}", pc_, "tab", [ccw(poly)],
                           self._glue_asm(P[target], P[names[src_i][0]].asm, e0, e1,
                                          tuple(beyond), tuple(into), below=True),
                           P[target].name, None, f"{lab}: {name.lower()} tab"))

        last = len(seq) - 1  # (the left side's back line again)
        if cut_cb:
            # a face: the back right's last facet tabbed under the back left's
            # first, at the back's centre (Birmingham's K under L)
            # (as wide as that facet's narrow end, so it stays on it)
            fwt = (Vector(pt2(i_cb, 1.0 - f_top, i_cb)) -
                   Vector(pt2(i_cb + 1, 1.0 - f_top, i_cb))).length
            end_tab("Close", i_cb - 1, i_cb, onward(i_cb, i_cb - 1), names[i_cb][0],
                    onward(i_cb, i_cb), pB, wide=0.9 * fwt)
        else:
            # closing tab off the last back facet, glued inside the left side
            end_tab("Close", last - 1, last, onward(last, last - 1), "FL_", onward(0, 0), pB)
        if two:  # the back strip's start, glued inside the right side
            end_tab("Join", i_split, i_split, -onward(i_split, i_split), "FR_",
                    -onward(i_split, i_split - 1), pB)
        # base tabs under the side walls, folded in (towards the fold) or out
        kk = 1.0 if m.get("tab_side", "IN") == "IN" else -1.0
        if m.get("face"):
            kk = -1.0  # (ears: out from the loop)
            j = max(1, min(n, round(float(m.get("face_width", 18.0)) /
                                    max(1e-6, (Vector(pt2(n, 1.0 - f_top, n)) -
                                               Vector(pt2(n + 1, 1.0 - f_top, n))).length))))
            top = pt2(n + 1, 1.0 - f_top, n)
            up2 = Vector(top) - Vector(pt2(n + 1, 1.0, n))
            self._muzzle(m, piece, P[names[n][0]], P[names[n + 1][0]], top, tuple(up2),
                         (P[names[n + 1 - j][0]], pt2(n + 1 - j, 1.0 - f_top, n + 1 - j)),
                         (P[names[n + j][0]], pt2(n + 1 + j, 1.0 - f_top, n + j)),
                         join=min(tb, 0.3 * float(m.get("face_len", 22.0))))
            self._forehead(m, piece, P, names, n, pt2, f_top)
        for nm, i, pg, Tp, sx in (("FL_", 0, host.p1, host.T1, -1.0),
                                  ("FR_", 2 * n + 1, host.p2, host.T2, 1.0)):
            e0, e1 = pt2(i, 1.0, i), pt2(i + 1, 1.0, i)
            ev = Vector(e1) - Vector(e0)
            Lb = ev.length
            ev = ev / Lb
            out_ = Vector(e0) - Vector(pt2(i, 1.0 - f_top, i))
            out_ = (out_ - out_.dot(ev) * ev).normalized()
            c2 = min(0.3 * tb, 0.2 * Lb)
            poly = [e0, e1, tuple(Vector(e1) + tb * out_ - c2 * ev),
                    tuple(Vector(e0) + tb * out_ + c2 * ev)]
            if m.get("face"):
                # leaning to the back (10 and 2 o'clock round the face) or the
                # front (8 and 4); 9 and 3 straight out
                ck = {"10": 1.0, "8": -1.0}.get(m.get("face_clock", "9"), 0.0)
                back = -ev if sx < 0 else ev  # (the left side's foot runs back to front)
                lean = math.radians(35.0) * ck
                o2 = math.cos(lean) * out_ + math.sin(lean) * back
                poly = self.ear(e0, e1, o2, float(m.get("face_ear", 22.0)))
            tgt = Tp.to_3x3() @ Vector((-sx * kk, 0.0, 0.0))
            sd = "L" if sx < 0 else "R"
            self.add(Panel(f"{piece}.Tab{sd}", piece, "tab", [ccw(poly)],
                           self._glue_asm(self.panels[pg], P[nm].asm, e0, e1, tuple(out_),
                                          (tgt.x, tgt.y)),
                           pg, None, f"{lab}: base tab {sd}"))
        self.line_frames[uid] = (piece, lambda q: q, None)
        if m.get("roof", "NONE") == "FLAT" and rt >= 1.0:
            r_ = 1.0 - f_top  # (the top's size over the bottom's: rt / a)
            iR = 2 * n + 1
            self._cone_lid(
                m, P["FL_"], P["FR_"], rt, ym - 0.5 * r_ * D, ym + 0.5 * r_ * D,
                # each side wall's top edge (back end, front end) and a point
                # on its foot, in its own pattern
                (pt2(0, r_, 0), pt2(1, r_, 0), pt2(0, 1.0, 0)),
                (pt2(iR + 1, r_, iR), pt2(iR, r_, iR), pt2(iR, 1.0, iR)))

    def _pair(self, m, host):
        """Two pieces of card glued back to back, on two parallel sticking
        strips (Birmingham 53): each glued down by a tab on a strip, bending
        up from it into the joined top, which stands on the mirror plane.
        The bend is low poly: each leg a run of narrow facets round a circular
        arc, as long as Leg Length, upright where the pieces meet. Shut, the
        legs are straight; open flat, they bend furthest."""
        uid, lab = m["uid"], m["label"]
        a, y0 = float(m["x"]), float(m["y"])
        W, Ht = float(m["depth"]), float(m["height"])
        Lb = max(1.0, float(m.get("pair_bend", 30.0)))
        tb = min(float(m.get("tab", 8.0)), 0.45 * Lb)
        kk = 1.0 if m.get("tab_side", "IN") == "OUT" else -1.0
        n = 8  # (the bend's facets)
        GMAX = 0.7246  # ((1 - cos f) / f at its largest)
        dmax = a * math.sin(math.radians(0.5 * min(180.0, self.tmax)))
        if dmax > GMAX * Lb:
            self.warn(f"{lab}: the legs are too short to bend out to the strips; make them "
                      f"at least {dmax / GMAX + 0.5:.0f} mm (or the strips closer)")
        if host.is_spine and a + Lb + Ht > self.W + 1e-6:
            self.warn(f"{lab}: strip distance + legs + top is more than the page width, so "
                      f"it sticks out when closed")
        if host.is_spine and (y0 < -1e-6 or y0 + W > self.H + 1e-6):
            self.warn(f"{lab}: runs past the top or bottom of the card")
        cache = {}

        def bend(t):
            """The arc's angle, radius and the junction, and the frame."""
            k_ = float(t)
            if k_ in cache:
                return cache[k_]
            S, e, xh, Y, sn, cs = self.strip_frame(host, t)
            q = min(GMAX - 1e-6, a * sn / Lb)
            lo, hi = 0.0, 2.3311
            for _ in range(60):
                md = 0.5 * (lo + hi)
                if (1.0 - math.cos(md)) / max(md, 1e-12) < q:
                    lo = md
                else:
                    hi = md
            phi = 0.5 * (lo + hi)
            res = (phi, S, e, xh, Y, sn, cs)
            if len(cache) > 4096:
                cache.clear()
            cache[k_] = res
            return res

        def arc_pt(t, s, u):
            """The leg's point u along it from the foot (s: -1 left, 1 right),
            in the plan (no Y)."""
            phi, S, e, xh, Y, sn, cs = bend(t)
            hdir = -s * xh  # (toward the mirror plane)
            foot = S + a * cs * e + s * a * sn * xh
            if phi < 1e-5:
                return foot + u * e
            R = Lb / phi
            J = foot + R * (1.0 - math.cos(phi)) * hdir + R * math.sin(phi) * e
            ps = phi * (1.0 - u / Lb)
            return J - R * hdir + R * (math.cos(ps) * hdir - math.sin(ps) * e)

        rows = [Lb * k / n for k in range(n + 1)]
        for s, pg, Tp, sd in ((-1.0, host.p1, host.T1, "L"), (1.0, host.p2, host.T2, "R")):
            piece = f"Tube{uid}" + ("" if s < 0 else "b")
            self.add_piece(Piece(piece, f"{lab} ({'left' if s < 0 else 'right'})",
                                 1 + uid if s < 0 else 350 + uid, (0.5 * W, 0.5 * Lb)))
            # printed side out: each piece's face away from the other
            _, S0, e0, xh0, Y0, _, _ = bend(90.0)
            sy = 1.0 if Y0.cross(e0).dot(s * xh0) > 0 else -1.0
            yc = y0 if sy > 0 else y0 + W
            lift = 0.25 * TAB_LIFT * s

            def asm_row(t, k, s=s, sy=sy, yc=yc):
                _, S, e, xh, Y, sn, cs = bend(t)
                p0 = arc_pt(t, s, rows[k]) + yc * Y
                p1 = arc_pt(t, s, rows[k + 1]) + yc * Y
                # (stretched the hair the chord is short of the arc, so the
                # facets meet edge to edge)
                sc = (p1 - p0).length / max(1e-9, rows[k + 1] - rows[k])
                return frame(p0, sy * Y, p1 - p0) @ Matrix.Diagonal((1.0, sc, 1.0, 1.0)) @ \
                    Matrix.Translation((0.0, -rows[k], 0.0))

            def asm_top(t, s=s, sy=sy, yc=yc, lift=lift):
                _, S, e, xh, Y, sn, cs = bend(t)
                J = arc_pt(t, s, Lb) + yc * Y + lift * xh
                return frame(J, sy * Y, e) @ Matrix.Translation((0.0, -Lb, 0.0))

            prev = None
            names_ = []
            for k in range(n):
                nm = f"{piece}.Leg{sd}{k + 1}"
                p_ = self.add(Panel(nm, piece, "panel",
                                    [[(0.0, rows[k]), (W, rows[k]), (W, rows[k + 1]),
                                      (0.0, rows[k + 1])]],
                                    lambda t, k=k, f=asm_row: f(t, k), prev or pg, None,
                                    f"{lab}: {'left' if s < 0 else 'right'} leg"))
                p_.free = True
                self.smooth_panels.add(nm)
                if prev:
                    pair = frozenset((prev, nm))
                    self.fold_kind[pair] = "skip"
                    self.facets.add(pair)
                prev = nm
                names_.append(nm)
            top = self.add(Panel(f"{piece}.Top{sd}", piece, "panel",
                                 [[(0.0, Lb), (W, Lb), (W, Lb + Ht), (0.0, Lb + Ht)]], asm_top,
                                 prev, None,
                                 f"{lab}: {'left' if s < 0 else 'right'} top (glued back to "
                                 f"back)"))
            top.free = True
            self.fold_kind[frozenset((prev, top.name))] = "skip"
            self.facets.add(frozenset((prev, top.name)))
            # the tab on the strip, folded out (away from the fold) or in
            ch = min(0.3 * tb, 0.2 * W)
            tab = [(0.0, 0.0), (W, 0.0), (W - ch, -tb), (ch, -tb)]
            zl = (-1.0 if self.normals_out(host) else 1.0) * TAB_LIFT
            col_x = Vector((0.0, sy, 0.0))
            col_y = Vector((-kk * s, 0.0, 0.0))
            col_z = col_x.cross(col_y)
            Mt = Matrix.Identity(4)
            for i, c_ in enumerate((col_x, col_y, col_z)):
                Mt[0][i], Mt[1][i], Mt[2][i] = c_
            Mt[0][3], Mt[1][3], Mt[2][3] = s * a, yc, zl
            Mt = Tp @ Mt

            def asm_tab(t, pa=self.panels[pg].asm, Mt=Mt):
                return pa(t) @ Mt

            tp = self.add(Panel(f"{piece}.Tab{sd}", piece, "tab", [tab], asm_tab, pg, None,
                                f"{lab}: tab {sd}"))
            self.fold_kind[frozenset((tp.name, names_[0]))] = "valley" if kk > 0 else \
                "mountain"

    def _forehead(self, m, piece, P, names, n, pt2, f_top):
        """A face's forehead join (Birmingham's M under N): a bite out of the
        foot of the front crease C, Forehead Join up it, its edges stuck
        together. Each side's forehead is creased off the loop from there to
        the ear's inner corner, and folds as a dart, like the muzzle."""
        Lf = float(m.get("face_brow", 0.0))
        if Lf < 1.0:
            return  # (an open arch: no join)
        lab = m["label"]
        iC = n + 1  # (C's line)
        foot = Vector(pt2(iC, 1.0, n))
        tip = Vector(pt2(iC, 1.0 - f_top, n))
        Lc = (tip - foot).length
        if Lf > 0.8 * Lc:
            self.warn(f"{lab}: the forehead join is longer than most of the nose's crease; "
                      f"shortened")
            Lf = 0.8 * Lc
        O = foot + (tip - foot).normalized() * Lf
        down = foot - O
        # creased from there to the foot Muzzle Width out each side (the
        # book's M and N: small, either side of C's top)
        fw = (Vector(pt2(iC, 1.0, n)) - Vector(pt2(iC - 1, 1.0, n))).length
        j = max(1, min(n, round(float(m.get("face_width", 18.0)) / max(1e-6, fw))))
        endL = Vector(pt2(iC - j, 1.0, iC - j))
        endR = Vector(pt2(iC + j, 1.0, iC + j - 1))
        dd = math.radians(max(0.0, min(60.0, float(m.get("face_dart", 15.0)))))
        # the forehead opens out flat with the loop's foot: its dart only as
        # wide as lets it (Nose Dart at most)
        pl_, pr_ = P[names[iC - j][0]], P[names[iC + j - 1][0]]
        pc_ = P[names[iC][0]]
        widest = 0.0
        for t in list(self.samples) + [self.tmax]:
            Pc = pc_.asm(t) @ Vector((O.x, O.y, 0.0))
            gl = (pl_.asm(t) @ Vector((endL.x, endL.y, 0.0)) - Pc).normalized()
            gr = (pr_.asm(t) @ Vector((endR.x, endR.y, 0.0)) - Pc).normalized()
            widest = max(widest, 0.5 * gl.angle(gr))
        th_ = min((endL - O).angle(down), (endR - O).angle(down))
        dd = max(0.0, min(dd, th_ - widest - math.radians(1.0)))
        polys = {}
        cut_by = {}
        for sx, end, rng in ((-1.0, endL, range(iC - j, iC)), (1.0, endR, range(iC, iC + j))):
            # the wall cut off below the crease O -> end, on C's side
            cr = (end - O).to_2d()
            nrm = Vector((-cr.y, cr.x))
            if nrm.dot((foot - O).to_2d()) > 0:
                nrm = -nrm  # (pointing away from C's foot: the side kept)
            region = []
            for i in rng:
                nm = names[i][0]
                pn = self.panels.get(f"{piece}.{nm}")
                if pn is None:
                    continue
                keep = clip_halfplane(pn.polys[0], tuple(nrm), nrm.dot(O.to_2d()))
                cut = clip_halfplane(pn.polys[0], tuple(-nrm), -nrm.dot(O.to_2d()))
                region += [Vector(q) for q in cut]
                if len(cut) >= 3:
                    cut_by.setdefault(sx, []).append(pn.name)
                if len(keep) >= 3:
                    pn.polys = [keep]
                else:
                    pn.polys = []
            if len(region) < 3:
                return
            # the forehead: that region less the dart, a wedge off C's line
            h2 = (end - O).normalized()
            th = h2.angle(down)
            across = (h2 - h2.dot(down.normalized()) * down.normalized()).normalized()
            s2 = math.cos(dd) * down.normalized() + math.sin(dd) * across
            sn = Vector((-s2.y, s2.x))
            if sn.dot(h2.to_2d() if hasattr(h2, "to_2d") else h2) < 0:
                sn = -sn
            hull = _hull2([q.to_2d() for q in region] + [O.to_2d()])
            poly = clip_halfplane(hull, tuple(sn.to_2d()), sn.to_2d().dot(O.to_2d()))
            if len(poly) < 3 or th <= dd or dd < math.radians(2.0):
                self.warn(f"{lab}: no room for the forehead join's dart")
                return
            dd_ = []
            for q in poly:  # (no repeated corners)
                if not dd_ or (Vector(q) - Vector(dd_[-1])).length > 1e-3:
                    dd_.append(tuple(q))
            if len(dd_) > 1 and (Vector(dd_[0]) - Vector(dd_[-1])).length < 1e-3:
                dd_.pop()
            # its edge on the page pulled in a little: the forehead dips as it
            # closes, where real card would curve
            Ov = O.to_2d()
            ek = end.to_2d()
            for k, q in enumerate(dd_):
                qv = Vector(q)
                if (qv - Ov).length > 1e-3 and (qv - ek).length > 1e-3:
                    qv = Ov + (qv - Ov) * max(0.0, 1.0 - 2.0 / max(1.0, (qv - Ov).length))
                    dd_[k] = tuple(qv)
            polys[sx] = dd_
        self._muzzle(m, piece, P[names[n][0]], P[names[n + 1][0]], O.to_2d()[:],
                     down.to_2d()[:], (P[names[iC - j][0]], endL.to_2d()[:]),
                     (P[names[iC + j - 1][0]], endR.to_2d()[:]), polys=polys,
                     dart_deg=math.degrees(dd),
                     names=("Brow", "forehead"),
                     join=min(float(m.get("tab", 10.0)), 0.3 * Lf))
        for sx, nms in cut_by.items():
            b_ = f"{piece}.Brow{'L' if sx < 0 else 'R'}"
            for nm in nms:
                self.fold_kind[frozenset((nm, b_))] = "valley"

    def _cone_lid(self, m, wl, wr, rt, y1, y2, edge_l, edge_r):
        """A lid on a cone: a flat roof the shape of its top, in two halves
        creased down the middle, each hinged on a side wall's top edge by a
        tab folded in off the wall and glued underneath.

        The side walls' tops are Top Radius x sin(t/2) from the mirror plane,
        so a half Top Radius wide reaches it Top Radius x cos(t/2) above
        (Peak) or below (Dip) its hinge, just as a tube's flat roof does: flat
        when the card is open, standing up or tucked inside when shut."""
        uid, lab = m["uid"], f"{m['label']} lid"
        k = 1.0 if m.get("roof_fold", "PEAK") == "PEAK" else -1.0
        eave = max(float(m.get("eave", 0.0)), 0.0)
        hb = float(m["height"])
        if k < 0 and rt > abs(hb) + 1e-6:
            self.warn(f"{lab}: a dipped lid tucks {rt:.0f} mm down inside walls only "
                      f"{abs(hb):.0f} mm tall; use Peak or taller walls")
        if k < 0 and eave > 0:
            self.warn(f"{lab}: a dipped lid can't overhang; made without its eave")
            eave = 0.0
        piece = f"Roof{uid}"
        self.add_piece(Piece(piece, lab, 300 + uid, (0.0, 0.5 * (y1 + y2))))
        # left half when open: the top's half circles each end (the cone's own
        # facets), a straight edge on the wall; x = -rt on the hinge, 0 on the crease
        R = rt + eave
        ph = [0.5 * math.pi * i / ROUND_FACETS for i in range(ROUND_FACETS + 1)]
        polyL = [(-R * math.cos(p), y2 + R * math.sin(p)) for p in reversed(ph)] + \
            [(-R * math.cos(p), y1 - R * math.sin(p)) for p in ph]
        polyR = [(-x, y) for x, y in polyL]

        def place(t):
            A = wl.asm(t) @ v3(edge_l[0])  # the walls' top edges, at their back ends
            B = wl.asm(t) @ v3(edge_l[1])
            A2 = wr.asm(t) @ v3(edge_r[0])
            Y = (A - B).normalized()
            X = A2 - A
            d = 0.5 * X.length
            e = X.cross(Y).normalized()
            if e.dot(A - wl.asm(t) @ v3(edge_l[2])) * (1.0 if hb > 0 else -1.0) < 0:
                e = -e  # (up: from the walls' feet to their tops)
            C = 0.5 * (A + A2) + k * math.sqrt(max(rt * rt - d * d, 0.0)) * e
            return C - y2 * Y, (C - A) / rt, (A2 - C) / rt, Y

        def asm_L(t):
            O, dL, dR, Y = place(t)
            return frame(O, dL, Y)

        def asm_R(t):
            O, dL, dR, Y = place(t)
            return frame(O, dR, Y)

        HL = self.add(Panel(f"{piece}.L", piece, "panel", [polyL], asm_L, wl.name, None,
                            f"{lab}: left half"))
        HR = self.add(Panel(f"{piece}.R", piece, "panel", [polyR], asm_R, wr.name, None,
                            f"{lab}: right half"))
        if HL is None or HR is None:
            self.warn(f"{lab}: too small to make")
            return
        HL.hinge = self._hinge_on(wl.name, asm_L, (-rt, y2), (-rt, y1))
        HR.hinge = self._hinge_on(wr.name, asm_R, (rt, y1), (rt, y2))
        HL.hinge.kink_ok = HR.hinge.kink_ok = True  # (as the cone's own walls)
        # tabs folded in off the wall tops, glued under the halves
        w = min(float(m.get("tab", 10.0)), rt - 1.0)
        if w < 3.0:
            self.warn(f"{lab}: too narrow at the top for the lid's tabs")
            return
        for sd, wall, half, (q0, q1, foot), into in (("L", wl, HL, edge_l, (1.0, 0.0)),
                                                     ("R", wr, HR, edge_r, (-1.0, 0.0))):
            e0, e1 = Vector(q0), Vector(q1)
            ev = (e1 - e0).normalized()
            up = 0.5 * (e0 + e1) - Vector(foot)
            up = (up - up.dot(ev) * ev).normalized()  # past the top, in the wall's pattern
            c = min(0.3 * w, 0.2 * (e1 - e0).length)
            poly = [tuple(e0), tuple(e1), tuple(e1 + w * up - c * ev),
                    tuple(e0 + w * up + c * ev)]
            self.add(Panel(f"Tube{uid}.Top{sd}", wall.piece, "tab", [ccw(poly)],
                           self._glue_asm(half, wall.asm, tuple(e0), tuple(e1), tuple(up),
                                          into, below=True),
                           half.name, None, f"{lab}: tab {sd}"))

    def _tube(self, m, host):
        """Tube on two parallel sticking strips (Birmingham 51, 67, 68). The
        side walls are glued to strips at distance a either side of the fold;
        the front and back are pairs of walls creased vertically above the
        fold, pointing Out (hexagon), In (recessed) or flat when the pair is
        as wide as the strips are apart (box)."""
        if m.get("pair"):
            self._pair(m, host)
            return
        uid, lab = m["uid"], m["label"]
        a, y0 = float(m["x"]), float(m["y"])
        D, hgt = float(m["depth"]), float(m["height"])
        rf = m.get("front_style", "OUT") == "ROUND"
        rb = m.get("back_style", "OUT") == "ROUND"
        rt = float(m.get("cone_top", 0.0) or 0.0)
        if m.get("face") and rf and rb and m.get("roof", "NONE") == "NONE" and (
                rt <= 0.05 or abs(rt - a) <= 0.5):
            # a face is always cut as Birmingham's one band: a loop leaning in
            # at least a little
            rt = max(1.0, a - hgt * math.tan(math.radians(3.0)))
        if rt > 0.05 and abs(rt - a) > 0.5:
            if rf and rb and m.get("roof", "NONE") in ("NONE", "FLAT"):
                self._cone(m, host, rt)
                return
            self.warn(f"{lab}: a different top radius needs a round front and back, and "
                      f"no roof or a flat one (a lid); made straight up")
        wf, wb = max(float(m["front"]), a), max(float(m["back"]), a)
        if float(m["front"]) < a - 1e-6 or float(m["back"]) < a - 1e-6:
            self.warn(f"{lab}: front and back walls must be at least as wide as the strip "
                      f"distance; widened to {a:.0f} mm")
        wmin = a / ROUND_FMAX + 0.01
        for on, w_, nm_ in ((rf, wf, "front"), (rb, wb, "back")):
            if on and w_ < wmin:
                self.warn(f"{lab}: a round {nm_} needs walls at least {wmin:.0f} mm wide "
                          f"for this strip distance ({0.5 * math.pi * a:.0f} mm makes it "
                          f"a half circle); widened")
        if rf:
            wf = max(wf, wmin)
        if rb:
            wb = max(wb, wmin)
        sf = 1.0 if m.get("front_style", "OUT") in ("OUT", "ROUND") else -1.0
        sb = 1.0 if m.get("back_style", "OUT") in ("OUT", "ROUND") else -1.0
        tb = min(float(m.get("tab", 10.0)), 0.45 * D)
        if sf < 0 and sb < 0 and wf + wb > D + 1e-6:
            self.warn(f"{lab}: recessed front and back meet inside the tube when closed "
                      f"(make it longer or the walls narrower)")
        if host.is_spine and a + hgt > self.W + 1e-6:
            self.warn(f"{lab}: strip distance + height is more than the page width, so it "
                      f"sticks out when closed")
        if host.is_spine and (y0 - sf * wf < -1e-6 or y0 + D + sb * wb > self.H + 1e-6):
            self.warn(f"{lab}: runs past the top or bottom of the card")
        nf = ROUND_FACETS if rf else 1
        nb = ROUND_FACETS if rb else 1
        self.tubes[uid] = dict(host=host, a=a, y0=y0, D=D, wf=wf, wb=wb, sf=sf, sb=sb, h=hgt,
                               label=lab, rf=rf, rb=rb, nf=nf, nb=nb)
        piece = f"Tube{uid}"
        self.add_piece(Piece(piece, lab, 1 + uid, (D + wf, 0.5 * hgt)))
        pts = lambda t: self.tube_plan(uid, t)
        # strip pattern: F_L | G_fl | G_fr | F_R | G_br | G_bl | closing tab
        u = [0.0, D, D + wf, D + 2 * wf, 2 * D + 2 * wf, 2 * D + 2 * wf + wb,
             2 * D + 2 * wf + 2 * wb]
        two = int(m.get("strips", 1) or 1) >= 2
        pR = f"{piece}b" if two else piece  # the right side wall and the back
        if two:
            # two strips: the left side and the front, the right side and the
            # back, each with a tab glued inside the other's side wall
            self.pieces[piece].label = f"{lab} (front)"
            self.pieces[piece].wrap = [0.0, 0.0, u[3], hgt]
            self.add_piece(Piece(pR, f"{lab} (back)", 350 + uid,
                                 (0.5 * (u[3] + u[6]), 0.5 * hgt)))
            self.pieces[pR].wrap = [u[3], 0.0, u[6], hgt]
        else:
            self.pieces[piece].wrap = [0.0, 0.0, u[6], hgt]  # all six walls, round
        # each front or back half: one wall, or facets round a curve (keys into
        # tube_plan, which gives the points between them)
        nodesL = ["FL"] + [f"fL{k}" for k in range(1, nf)] + ["CF"]
        nodesR = ["CF"] + [f"fR{k}" for k in range(nf - 1, 0, -1)] + ["FR"]
        nodesBR = ["BR"] + [f"bR{k}" for k in range(1, nb)] + ["CB"]
        nodesBL = ["CB"] + [f"bL{k}" for k in range(nb - 1, 0, -1)] + ["BL"]
        segs = [("FL_", "FL_", u[0], u[1], "BL", "FL", "left side")]

        def half(key, nodes, u0, w, n, lb):
            for k in range(n):
                nm_ = key if n == 1 else f"{key}{k + 1}"
                segs.append((nm_, key, u0 + w * k / n, u0 + w * (k + 1) / n, nodes[k],
                             nodes[k + 1], lb if n == 1 else f"{lb} {k + 1}"))

        half("GFL", nodesL, u[1], wf, nf, "front left")
        half("GFR", nodesR, u[2], wf, nf, "front right")
        segs.append(("FR_", "FR_", u[3], u[4], "FR", "BR", "right side"))
        half("GBR", nodesBR, u[4], wb, nb, "back right")
        half("GBL", nodesBL, u[5], wb, nb, "back left")
        frame_fn = None
        if rf or rb:  # many facets ask for the same openings: work each out once
            fc = {}

            def frame_fn(t):
                k = float(t)
                if k not in fc:
                    if len(fc) > 4096:
                        fc.clear()
                    fc[k] = self.strip_frame(host, t)
                return fc[k]
        walls = {}
        for nm, grp, u0, u1, pk, qk, lb in segs:
            poly = [(u0, 0), (u1, 0), (u1, hgt), (u0, hgt)]
            walls[nm] = dict(poly=poly, asm=self._wall_asm(host, a, pk, qk, u0, pts, frame_fn),
                             u0=u0,
                             u1=u1, grp=grp, lb=lb, ends=(pk, qk))
        tab_hinge = lambda u_: hinge_frame_2d((u_, 0), (0, 1))
        P = {}
        # side walls hinge on the strips
        P["FL_"] = self.add(Panel(f"{piece}.FL_", piece, "panel", [walls["FL_"]["poly"]],
                                  walls["FL_"]["asm"], host.p1,
                                  Hinge(host.T1 @ hinge_frame_2d((-a, y0 + D), (0, -1)),
                                        hinge_frame_2d((0, 0), (1, 0))),
                                  f"{lab}: left side"))
        P["FR_"] = self.add(Panel(f"{piece}.FR_", pR, "panel", [walls["FR_"]["poly"]],
                                  walls["FR_"]["asm"], host.p2,
                                  Hinge(host.T2 @ hinge_frame_2d((a, y0), (0, 1)),
                                        hinge_frame_2d((u[3], 0), (1, 0))),
                                  f"{lab}: right side"))
        # the rest chain on from the side walls: front from the left, back from the right
        chain = [sg[0] for sg in segs]
        i_fr = chain.index("FR_")
        for order_ in (chain[1:i_fr], chain[i_fr + 1:]):
            prev = "FL_" if order_ and order_[0].startswith("GF") else "FR_"
            pc_ = piece if prev == "FL_" else pR
            for nm in order_:
                w_ = walls[nm]
                P[nm] = self.add(Panel(f"{piece}.{nm}", pc_, "panel", [w_["poly"]],
                                       w_["asm"], P[prev].name,
                                       Hinge(tab_hinge(w_["u0"]), tab_hinge(w_["u0"]),
                                             "TABLE", {}),
                                       f"{lab}: {w_['lb']}"))
                if walls[prev]["grp"] == w_["grp"] and nm != w_["grp"]:
                    # facets of one curved wall: one sheet, no fold drawn between them
                    pair = frozenset((P[prev].name, P[nm].name))
                    self.fold_kind[pair] = "skip"
                    self.facets.add(pair)
                if nm != w_["grp"]:
                    self.smooth_panels.add(P[nm].name)
                prev = nm
        # where a point sits along the strip, on the wall a tether glues to
        self.tubes[uid]["walls"] = {nm: (P[nm].name, w_["u0"], w_["u1"]) + w_["ends"]
                                    for nm, w_ in walls.items()}
        if m.get("face"):
            self._tube_face(m, piece, P, u[2], hgt, nf, wf)
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

        self.add(Panel(f"{piece}.Close", pR, "tab", [close], asm_close, P["FL_"].name, None,
                       f"{lab}: closing tab"))
        if two:  # the front strip's end, glued inside the right side wall
            join = [(u[3], 0), (u[3] + tb, ch), (u[3] + tb, hgt - ch), (u[3], hgt)]
            Pj = frame(Vector((u[3], 0, 0)), (1, 0, 0), (0, 1, 0)).inverted()

            def asm_join(t):
                p = pts(t)
                S, e, xh, Y, sn, cs = self.strip_frame(host, t)
                f3 = self.plan3d(host, a, t, p["FR"])
                b3 = self.plan3d(host, a, t, p["BR"])
                return frame(f3 - TAB_LIFT * xh, (b3 - f3).normalized(), e) @ Pj

            self.add(Panel(f"{piece}.Join", piece, "tab", [join], asm_join, P["FR_"].name,
                           None, f"{lab}: joining tab"))
        # base tabs under the side walls, folded in (towards the fold) or out
        k = 1.0 if m.get("tab_side", "IN") == "IN" else -1.0
        if m.get("face"):
            k = -1.0  # (ears: out from the loop)
        for side, u0, u1, T, parent, Tp in (
            ("L", u[0], u[1], frame(Vector((-a, y0 + D, TAB_LIFT)), (0, -1, 0), (-k, 0, 0)),
             host.p1, host.T1),
            ("R", u[3], u[4], frame(Vector((a, y0, TAB_LIFT)), (0, 1, 0), (k, 0, 0)),
             host.p2, host.T2),
        ):
            T = T @ frame(Vector((u0, 0, 0)), (1, 0, 0), (0, 1, 0)).inverted()
            tbb = float(m.get("tab", 10.0))  # (out from the wall: not limited by its length)
            c2 = min(0.3 * tbb, 0.2 * D)
            poly = [(u0 + c2, -tbb), (u0, 0), (u1, 0), (u1 - c2, -tbb)]
            if m.get("face"):
                poly = self.ear((u0, 0.0), (u1, 0.0), (0.0, -1.0),
                                float(m.get("face_ear", 22.0)))
            sgn = -1.0 if side == "L" else 1.0
            n2 = (sgn * T[0][0], sgn * T[0][1])
            poly = clip_halfplane(poly, n2, 0.5 - sgn * T[0][3])
            pa = self.panels[parent].asm
            Tpat = Tp @ T
            self.add(Panel(f"{piece}.Tab{side}", piece if side == "L" else pR, "tab", [poly],
                           (lambda t, pa=pa, T=Tpat: pa(t) @ T), parent, None,
                           f"{lab}: base tab {side}"))
        # the folds where the side walls meet the page, outside the tube
        self._wall_host(uid, "WL", P["FL_"].name, (0.0, 0.0), (1.0, 0.0), (0.0, 1.0),
                        host.p1, host.T1, (-a, y0 + D), (0.0, -1.0), (-1.0, 0.0),
                        f"{lab}: left side wall", (D, hgt))
        self._wall_host(uid, "WR", P["FR_"].name, (u[3], 0.0), (1.0, 0.0), (0.0, 1.0),
                        host.p2, host.T2, (a, y0), (0.0, 1.0), (1.0, 0.0),
                        f"{lab}: right side wall", (D, hgt))
        creases = tuple(k_ for k_, ok_ in (
            ("KF", not rf and sf > 0 and wf > a + 0.5),
            ("KB", not rb and sb > 0 and wb > a + 0.5)) if ok_)
        self._corner_hosts(uid, lab, P, u, hgt, walls, creases)
        # which wall a tether glues to at each point, and the way along it
        cfw = "GFL" if nf == 1 else f"GFL{nf}"
        cbw = "GBR" if nb == 1 else f"GBR{nb}"
        self.tubes[uid]["attach"] = dict(
            FL=(P["FL_"].name, "BL"), BL=(P["FL_"].name, "FL"),
            FR=(P["FR_"].name, "BR"), BR=(P["FR_"].name, "FR"),
            CF=(P[cfw].name, walls[cfw]["ends"][0]), CB=(P[cbw].name, walls[cbw]["ends"][0]))
        roof = m.get("roof", "NONE")
        roof = {True: "POINTED", False: "NONE"}.get(roof, roof)
        if roof == "GABLE":
            self.warn(f"{lab}: gabled roofs go on towers (a tube's ends don't keep their "
                      f"distance as it folds); use Pointed or Flat")
        elif roof == "POINTED" and (rf or rb):
            self.warn(f"{lab}: a pointed roof needs straight front and back walls; use a "
                      f"flat roof on a round tube")
        elif roof == "POINTED":
            self._roof(uid, f"Roof{uid}", f"{lab} roof", 300 + uid, host, a, y0, D, wf, wb,
                       sf, sb, hgt, float(m.get("roof_height", 30.0)),
                       float(m.get("ridge", 0.0)), tb, "IN",
                       walls=(P["FL_"].name, P["FR_"].name))
        elif roof == "FLAT":
            self._flat_roof(uid, f"{lab} roof", host, a, y0, D, wf, wb, sf, sb, hgt,
                            float(m.get("eave", 0.0)), m.get("roof_fold", "PEAK"), tb,
                            P["FL_"], P["FR_"], u[3], float(m.get("rib", 0.0)), uid)
