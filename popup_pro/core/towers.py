"""Castle towers' tops: pointed, gabled and flat roofs, battlements and
ledges."""
import math

from mathutils import Matrix, Vector

from .base import Hinge, Host, Panel, Piece, poly_area, TAB_LIFT
from .geom import Z, ccw, clip_halfplane, frame, hinge_frame_2d, v3


class Towers:
    """Tower roof builders. Mixed into Model (model.py)."""

    @staticmethod
    def _peak(polys, T, lo, hi, top, rise):
        """Raise a gable on the top edge of a panel between x = lo and hi
        (coordinates through T, pattern -> local): its apex rise above top,
        half-way. Returns the new polys (pattern coordinates)."""
        Ti = T.inverted()
        out = []
        for poly in polys:
            V = [(Ti @ v3(q)).to_2d()[:] for q in poly]
            n = len(V)
            done = False
            for i in range(n):
                if done:
                    break
                P, Q = V[i], V[(i + 1) % n]
                if abs(P[1] - top) > 1e-4 or abs(Q[1] - top) > 1e-4:
                    continue
                if min(P[0], Q[0]) > lo + 1e-4 or max(P[0], Q[0]) < hi - 1e-4:
                    continue
                pts = [(lo, top), (0.5 * (lo + hi), top + rise), (hi, top)]
                if P[0] > Q[0]:
                    pts.reverse()
                pts = [q for q in pts if (q[0] - P[0]) ** 2 + (q[1] - P[1]) ** 2 > 1e-8 and
                       (q[0] - Q[0]) ** 2 + (q[1] - Q[1]) ** 2 > 1e-8]
                V = V[:i + 1] + pts + V[i + 1:]
                done = True
                break
            out.append([(T @ Vector((x, y, 0.0))).to_2d()[:] for x, y in V])
        return out

    def _tower_gable(self, m, host, base, a, b, y0, w, tab):
        """Birmingham 49's roof on a corner tower. The tower is a
        parallelogram: a wall and the inner face across from it stay
        parallel as it shears. Each of that pair gets a gable end; a rib
        joins the two tips (the only points that keep their places to each
        other) on vertical folds, and a roof creased along its ridge is
        stuck on tabs on the rib's top, glued to nothing else. The gables'
        slopes hold its halves up, square open, and let them hang down
        flat as the tower shears flat; it overhangs the walls all round
        (Overhang), so nothing snags as it closes."""
        uid, lab = m["uid"], m["label"]
        rise = max(1.0, float(m.get("roof_height", 0.0) or 0.6 * min(a, b)))
        eave = max(0.0, float(m.get("eave", 0.0) or 0.0))
        turn = bool(m.get("gable_turn", False))
        AC, CB = self._tw_pair(base)
        if AC not in self.panels or CB not in self.panels:
            return
        top = y0 + w
        if not turn:  # gables on the left wall (S to A) and on CB; the ridge runs along b
            wall, Tw, lo, hi = host.p1, host.T1, -a, 0.0
            inner, ilo, ihi = CB, b, a + b
            span, L = a, b
        else:  # on the right wall (S to B) and on AC; the ridge runs along a
            wall, Tw, lo, hi = host.p2, host.T2, 0.0, b
            inner, ilo, ihi = AC, 0.0, b
            span, L = b, a
        Tin, itop = Matrix.Identity(4), w
        if base in self.__dict__.get("_tw", {}):
            # a cube's back wall: the wall itself moved across the house, so
            # the wall's own coordinates carry over to it
            S, l, r, Y, nl, nr = host.dirs(self.t_ref)
            shift = Matrix.Translation(L * (l if turn else r))
            Tin = self.panels[inner].asm(self.t_ref).inverted() @ shift @ \
                self.panels[wall].asm(self.t_ref) @ Tw
            ilo, ihi, itop = lo, hi, top
        # the gables (box pattern: u across, v up the corner from y0)
        pw = self.panels[wall]
        pw.polys = [ccw(q) for q in self._peak(pw.polys, Tw, lo, hi, top, rise)]
        pin = self.panels[inner]
        pin.polys = [ccw(q) for q in self._peak(pin.polys, Tin, ilo, ihi, itop, rise)]

        def wpt(t, x, y):  # a point on the wall gable, virtual coordinates
            return self.panels[wall].asm(t) @ (Tw @ Vector((x, y, 0.0)))

        def geo(t):
            E1 = wpt(t, 0.5 * (lo + hi), top + rise)
            E2 = self.panels[inner].asm(t) @ (Tin @ Vector((0.5 * (ilo + ihi), itop + rise, 0.0)))
            v = (E2 - E1).normalized()
            S, l, r, Y, nl, nr = host.dirs(t)
            ds = []
            for x in (lo, hi):
                d = wpt(t, x, top) - E1
                d = d - d.dot(v) * v
                ds.append(rest(t, E1, v, d.normalized()))
            return E1, E2, v, Y, ds

        reach = {}  # (set once the roof's size is known)

        def rest(t, E1, v, d):
            """A roof half hangs on its gables' slopes (d, down from the
            ridge), unless a page is in the way: then it rests on the page,
            turned up about the ridge just far enough."""
            if not reach:
                return d
            _, _, nl, nr = self.dirs(t)
            ends = [E1 + x * v for x in reach["x"]]

            def clear(dd):
                return min((e + reach["s"] * dd).dot(n) for e in ends for n in (nl, nr))

            if clear(d) >= 0.0:
                return d
            k = v.cross(d)
            if clear(d + 0.02 * k) < clear(d - 0.02 * k):
                k = -k

            def at(a_):
                return d * math.cos(a_) + k * math.sin(a_)

            N = 48
            ok = next((i for i in range(1, N + 1) if clear(at(math.pi * i / N)) >= 0.0), None)
            if ok is None:  # (no room anywhere: where it's least in the way)
                return at(max((math.pi * i / N for i in range(N + 1)),
                              key=lambda a_: clear(at(a_)))).normalized()
            lo_, hi_ = math.pi * (ok - 1) / N, math.pi * ok / N
            for _ in range(30):
                mid = 0.5 * (lo_ + hi_)
                if clear(d * math.cos(mid) + k * math.sin(mid)) >= 0.0:
                    hi_ = mid
                else:
                    lo_ = mid
            return (d * math.cos(hi_) + k * math.sin(hi_)).normalized()

        tr = self.t_ref
        E1, E2, v, Y, ds = geo(tr)
        if abs((E2 - E1).length - L) > 0.5:
            self.warn(f"{lab}: the gable tips don't keep their distance; no roof")
            return
        # which corner each half rests on: printed side up
        k0 = 0 if v.cross(ds[0]).dot(Y) > 0 else 1
        # (the slope's true length along the roof: corner to ridge, square to it)
        Eo, E2o, vo, _, _ = geo(self.tmax)
        S0 = max(1.0, max(((wpt(self.tmax, x, top) - Eo) -
                           (wpt(self.tmax, x, top) - Eo).dot(vo) * vo).length for x in (lo, hi)))
        hr = max(3.0, min(0.6 * rise, 12.0))  # the rib, down from the ridge
        tb = max(3.0, min(tab, 0.45 * span, 10.0))
        rp = f"Rib{uid}"
        self.add_piece(Piece(rp, f"{lab} roof rib", 400 + uid, (0.5 * L, 0.0)))

        def asm_rib(t):
            E1, E2, v, Y, ds = geo(t)
            return frame(E1, v, Y)

        # the rib hinges on the wall gable's tip, on a fold up the gable
        Hp = Tw @ hinge_frame_2d((0.5 * (lo + hi), top + rise), (0.0, 1.0))
        Fc = hinge_frame_2d((0.0, 0.0), (0.0, 1.0))
        rib = self.add(Panel(f"{rp}.Rib", rp, "panel", [[(0.0, -hr), (L, -hr), (L, 0.0),
                                                         (0.0, 0.0)]], asm_rib, wall,
                             Hinge(Hp, Fc, "TABLE", {}), f"{lab}: roof rib"))
        rib.hinge.host_bound = True
        # its end tabs, glued flat on the two gables (inside)
        for end, x0, sgn, par in (("A", 0.0, -1.0, wall), ("B", L, 1.0, inner)):
            # inside the gable's point: as wide as its slopes allow
            tx = min(tb, 0.9 * hr * 0.5 * span / rise)
            if end == "A":
                poly = [(-tx, -hr), (0.0, -hr), (0.0, 0.0)]
            else:
                poly = [(L, -hr), (L + tx, -hr), (L, 0.0)]
            Pa = self.panels[par].asm(tr)
            gx = (Pa.to_3x3() @ Vector((1.0, 0.0, 0.0))).normalized()  # along the gable
            gn = (Pa.to_3x3() @ Z).normalized()
            if gx.dot(v) * sgn < 0:
                gx = -gx
            if gn.dot(v) * sgn > 0:
                gn = -gn  # the side the rib is on
            E = E1 if end == "A" else E2
            own = frame(E + TAB_LIFT * gn, gx, Y) @ \
                frame(Vector((x0, 0.0, 0.0)), (sgn, 0.0, 0.0), (0.0, 1.0, 0.0)).inverted()
            off = Pa.inverted() @ own
            self.add(Panel(f"{rp}.Tab{end}", rp, "tab", [poly],
                           (lambda t, f=self.panels[par].asm, off=off: f(t) @ off), par, None,
                           f"{lab}: rib tab {end}"))
        # the roof: one sheet creased along its ridge, overhanging all round
        fp = f"GRoof{uid}"
        self.add_piece(Piece(fp, f"{lab} roof", 450 + uid, (0.5 * L, 0.0)))
        Sx = S0 + eave
        reach.update(x=(-eave, L + eave), s=Sx)
        halfA = [(-eave, 0.0), (L + eave, 0.0), (L + eave, Sx), (-eave, Sx)]
        halfB = [(-eave, -Sx), (L + eave, -Sx), (L + eave, 0.0), (-eave, 0.0)]

        def asm_A(t):
            E1, E2, v, Y, ds = geo(t)
            return frame(E1, v, ds[k0])

        def asm_B(t):
            E1, E2, v, Y, ds = geo(t)
            return frame(E1, v, -ds[1 - k0])

        ridge = hinge_frame_2d((0.0, 0.0), (1.0, 0.0))
        RA = self.add(Panel(f"{fp}.A", fp, "panel", [halfA], asm_A, rib.name,
                            Hinge(ridge, ridge, "TABLE", {}), f"{lab}: roof"))
        RB = self.add(Panel(f"{fp}.B", fp, "panel", [halfB], asm_B, RA.name,
                            Hinge(ridge, ridge, "TABLE", {}), f"{lab}: roof"))
        RA.hinge.host_bound = RB.hinge.host_bound = True
        RA.hinge.kink_ok = RB.hinge.kink_ok = True  # (a half lifts off its gables onto a page)
        # tabs on top of the rib, folded either way and stuck under the halves
        tw = min(tb, 0.4 * S0)
        g = min(2.0, 0.1 * L)
        c = 0.3 * tw
        for half, x0, x1, kk, lab2 in ((RA, g, 0.5 * L - g, k0, "A"),
                                       (RB, 0.5 * L + g, L - g, 1 - k0, "B")):
            poly = [(x0, 0.0), (x1, 0.0), (x1 - c, tw), (x0 + c, tw)]

            def asm_t(t, kk=kk):
                E1, E2, v, Y, ds = geo(t)
                n = v.cross(ds[kk]).normalized()
                if n.dot(Y) < 0:
                    n = -n
                return frame(E1 - TAB_LIFT * n, v, ds[kk])

            self.add(Panel(f"{rp}.Top{lab2}", rp, "tab", [poly], asm_t, half.name, None,
                           f"{lab}: rib top tab {lab2}"))

    def _tower_roof(self, m, host, base, a, b, y0, w, tab, flat=False):
        """A pyramid (or near-flat) roof on a corner tower that still folds
        flat: two V-folds, one in each of the two corners of the tower that
        close to 0 degrees as the card shuts (where V-folds lie flat), hinged
        on the two top edges that meet there (glue lines square to the
        corner) with their creases rising to the apex over the tower's
        middle. Open flat the four faces meet in a pyramid; part-way they
        part along the two hips. In a tube's side corners those are the
        tower's side corners (A, B); on a front or back crease, where the
        corner itself closes, its own corner and the inner one (S, C).
        Flat: the apex only Slope above the top (or below it, a dish, so the
        crease is a valley on top), the roof set Below Top inside the tower
        (Battlements on the walls above), and at the top an Overhang: a
        ledge stuck over the roof reaching past the walls all round."""
        uid, lab = m["uid"], m["label"]
        if abs(a - b) > 0.5:
            # (an oblong one's V-folds can't follow it nearly shut)
            self.warn(f"{lab}: a pointed or flat roof needs a square tower (the same "
                      f"distance along both walls; a gabled roof doesn't); no roof")
            return
        tr = self.tmax
        S0, l0, r0, Y0, nl, nr = host.dirs(tr)
        top = y0 + w
        below = max(0.0, float(m.get("roof_below", 0.0) or 0.0)) if flat else 0.0
        below = min(below, 0.8 * w)
        yv = top - below
        if flat:
            rise = float(m.get("roof_slope", 1.5))
            if abs(rise) < 0.3:
                rise = 0.3 if rise >= 0 else -0.3
                self.warn(f"{lab}: a flat roof needs a little slope to fold the right way; "
                          f"0.3 mm")
        else:
            s_ = 0.5 * (a + b)
            rise = max(1.0, float(m.get("roof_height", 0.6 * s_) or 0.6 * s_))
        # (virtual y runs up the corner from the page)
        S = S0 + yv * Y0
        A = S + a * l0
        B = S + b * r0
        C = A + b * r0
        O = 0.5 * (S + C) + rise * Y0
        # which pair of the tower's corners closes as the card shuts
        S1, l1, r1, _, _, _ = host.dirs(max(2.0, 0.1 * tr))
        opening = l1.angle(r1) > l0.angle(r0)
        AC, CB = self._tw_pair(base)
        if AC not in self.panels or CB not in self.panels:
            return
        rt = min(tab, 0.4 * w)
        if below > 0:  # (under the battlements' notches)
            rt = min(rt, 0.4 * (w - below), below - self._crenel_depth(a, b, below) - 0.5)
            rt = max(rt, 2.0)
        if opening:
            for tn in (f"{base}.TabA", f"{base}.TabB"):
                # the tower's own tabs stop short of the roof's tabs (both glue
                # inside the walls; the roof's hang down from its edges)
                if tn in self.panels:
                    p_ = self.panels[tn]
                    lim = w - below - rt - 1.0
                    p_.polys = [ccw(q) for q in (clip_halfplane(q, (0.0, -1.0), -lim)
                                                 for q in p_.polys) if len(q) >= 3]
        corners = self._tower_vcorners(host, base, a, b, y0, lab, "roof", opening,
                                       S, A, B, C)
        made = []
        for k, (hc, X, PL, PR) in enumerate(corners):
            hc.finish()
            hc.trig = False
            gl, gr = (PL - X).length, (PR - X).length
            L = (O - X).length
            al = math.degrees((PL - X).angle(O - X))
            ar = math.degrees((PR - X).angle(O - X))
            n0 = len(self.order)
            self._vfold(dict(uid=f"{uid}r{k}", type="VFOLD", label=f"{lab} roof",
                             y=yv, phi_l=90.0, phi_r=90.0, alpha_l=al, alpha_r=ar,
                             glue=gl, glue_r=gr, height=L, tab=rt, shape="TRI",
                             tab_side="OUT", pref=(0.0, 1.0 if rise > 0 else -1.0),
                             slot=800 + 2 * uid + k), hc)
            for name in self.order[n0:]:
                hg = self.panels[name].hinge
                if hg is not None and hg.kind in ("LINEAR", "SPHERICAL", "EXPR"):
                    hg.kind = "TABLE"
                if hg is not None:
                    hg.host_bound = True
            made.append([n for n in self.order[n0:] if n.endswith((".HalfL", ".HalfR"))])
        if flat and below > 0 and m.get("battlements", True):
            self._tower_crenels(m, host, base, a, b, y0, w, below)
        eave = float(m.get("eave", 0.0) or 0.0) if flat else 0.0
        if eave > 0 and below > 0:
            self.warn(f"{lab}: a roof set below the top can't overhang the walls; "
                      f"no overhang")
        elif eave > 0:
            self._tower_ledge(m, made, eave, Y0)

    def _tw_pair(self, base):
        """A tower's two inner walls (the box fold's panels; a cube's back walls)."""
        o = self.__dict__.get("_tw", {}).get(base)
        return (o["AC"], o["CB"]) if o else (f"{base}.AC", f"{base}.CB")

    def _tower_vcorners(self, host, base, a, b, y0, lab, what, opening, S, A, B, C):
        """The tower's two corners that close to 0 as the card shuts (where a
        V-fold folds flat), each as a Host with its corner point and the
        points along its left and right walls: A and B in a tube's side
        corners, S and C on a crease."""
        AC, CB = self._tw_pair(base)
        R = Matrix.Rotation(math.pi, 4, "Y")
        o = self.__dict__.get("_tw", {}).get(base)
        if o and not opening:  # (a cube: its back walls' own placements)
            return ((Host(self, host.p1, 0.0, 0.0, host.p2, 0.0, 0.0,
                          f"{lab}: {what} corner S", host.T1, host.T2), S, A, B),
                    (Host(self, AC, 0.0, 0.0, CB, 0.0, 0.0, f"{lab}: {what} corner C",
                          *o["TC"]), C, A, B))
        if opening:
            return (
                # at A: the box's top panel (left) and the wall back towards the corner
                (Host(self, AC, 0.0, 0.0, host.p1, 0.0, 0.0, f"{lab}: {what} corner A",
                      Matrix.Translation((0.0, -y0, 0.0)) @ R,
                      host.T1 @ Matrix.Translation((-a, 0.0, 0.0))), A, C, S),
                # at B: the other wall back towards the corner (left) and the front panel
                (Host(self, host.p2, 0.0, 0.0, CB, 0.0, 0.0, f"{lab}: {what} corner B",
                      host.T2 @ Matrix.Translation((b, 0.0, 0.0)),
                      Matrix.Translation((a + b, -y0, 0.0)) @ R), B, S, C))
        return (
            # at S: the corner itself, the two walls
            (Host(self, host.p1, 0.0, 0.0, host.p2, 0.0, 0.0, f"{lab}: {what} corner S",
                  host.T1, host.T2), S, A, B),
            # at C: the box's two panels
            (Host(self, AC, 0.0, 0.0, CB, 0.0, 0.0, f"{lab}: {what} corner C",
                  Matrix.Translation((b, -y0, 0.0)),
                  Matrix.Translation((b, -y0, 0.0))), C, A, B))

    @staticmethod
    def _cut_line(pa, pb, t):
        """Where pb's plane crosses pa's polygon at opening t, in pa's
        pattern coordinates (two points), or None."""
        Mb = pb.asm(t)
        o, n = Mb.translation, (Mb.to_3x3() @ Z).normalized()
        Mi = pa.asm(t).inverted()
        oo, nn = Mi @ o, Mi.to_3x3() @ n
        poly = pa.polys[0]
        pts = []
        for i in range(len(poly)):
            a_, b_ = Vector((*poly[i], 0.0)), Vector((*poly[(i + 1) % len(poly)], 0.0))
            da, db = (a_ - oo).dot(nn), (b_ - oo).dot(nn)
            if abs(da) < 1e-9:
                pts.append(a_.to_2d())
            elif da * db < 0:
                pts.append((a_ + (b_ - a_) * (da / (da - db))).to_2d())
        return pts[:2] if len(pts) >= 2 else None

    @staticmethod
    def _side_of(P, E, poly):
        """The half-plane (normal, offset) through P and E keeping most of
        poly."""
        d = (E - P).normalized()
        n = Vector((-d.y, d.x))
        c = Vector((sum(q[0] for q in poly) / len(poly), sum(q[1] for q in poly) / len(poly)))
        if (c - P).dot(n) < 0:
            n = -n
        return (n.x, n.y), n.dot(P)

    @staticmethod
    def _crenel_depth(a, b, below):
        return min(0.6 * below, max(2.0, 0.12 * min(a, b)), 6.0)

    def _tower_crenels(self, m, host, base, a, b, y0, w, below):
        """Battlements round a tower's top, above its sunken roof: merlons at
        both ends of each face, notches cut between."""
        top = y0 + w
        depth = self._crenel_depth(a, b, below)

        def notch(polys, T, lo, hi, top_):
            # the top cut down by the notches' depth, merlons standing on it
            # as their own (convex) pieces of the same sheet
            n = max(3, int(round((hi - lo) / 6.0)))
            n += 1 - n % 2  # odd: a merlon at each end
            seg = (hi - lo) / n
            Ti = T.inverted()
            out = []
            for poly in polys:
                V = [(Ti @ v3(q)).to_2d()[:] for q in poly]
                if not any(abs(y - top_) < 1e-4 and lo - 1e-4 <= x <= hi + 1e-4 for x, y in V):
                    out.append(V)
                    continue
                left = clip_halfplane(V, (-1.0, 0.0), -lo)
                mid = clip_halfplane(clip_halfplane(V, (1.0, 0.0), lo), (-1.0, 0.0), -hi)
                right = clip_halfplane(V, (1.0, 0.0), hi)
                mid = [(x, top_ - depth if y > top_ - 1e-6 else y) for x, y in mid]
                for part in (left, mid, right):
                    if len(part) >= 3 and abs(poly_area(part)) > 1e-6:
                        out.append(part)
                for i in range(0, n, 2):
                    x0, x1 = lo + i * seg, lo + (i + 1) * seg
                    out.append([(x0, top_ - depth), (x1, top_ - depth), (x1, top_), (x0, top_)])
            return [[(T @ Vector((x, y, 0.0))).to_2d()[:] for x, y in q] for q in out]

        for pn, T, lo, hi, tp in ((host.p1, host.T1, -a, 0.0, top), (host.p2, host.T2, 0.0, b, top),
                                  (f"{base}.AC", Matrix.Identity(4), 0.0, b, w),
                                  (f"{base}.CB", Matrix.Identity(4), b, a + b, w)):
            if pn in self.panels:
                p_ = self.panels[pn]
                p_.polys = [ccw(q) for q in notch(p_.polys, T, lo, hi, tp)]
        for tn in (f"{base}.TabA", f"{base}.TabB"):
            # the tower's tabs stop under the notches
            if tn in self.panels:
                p_ = self.panels[tn]
                p_.polys = [ccw(q) for q in (clip_halfplane(q, (0.0, -1.0), -(w - depth - 0.5))
                                             for q in p_.polys) if len(q) >= 3]

    def _tower_ledge(self, m, made, eave, up):
        """A flat tower roof's overhang: a sheet stuck over each V-fold's two
        halves, the same triangles grown out past the walls, creased along
        the same line. It moves with the roof, so it folds flat with it; open
        flat it makes a ledge round the tower's top."""
        uid, lab = m["uid"], m["label"]
        tr = self.t_ref
        for k, halves in enumerate(made):
            if len(halves) != 2:
                continue
            piece = f"Ledge{uid}x{k}"
            self.add_piece(Piece(piece, f"{lab} ledge {k + 1}", 960 + 2 * uid + k, (0.0, 0.0)))
            # the halves: (0, 0) the corner, Q the apex, G the glue line's end
            tri = []
            for hn in halves:
                poly = self.panels[hn].polys[0]
                Q = next(Vector(q) for q in poly if abs(q[0]) < 1e-6 and q[1] > 1e-6)
                G = next(Vector(q) for q in poly
                         if Vector(q).length > 1e-6 and (Vector(q) - Q).length > 1e-6)
                d = abs((G.x * Q.y - G.y * Q.x)) / max(G.length, 1e-9)  # Q to line O-G
                tri.append((hn, Q, G, (d + eave) / max(d, 1e-6)))
            fmax = max(f for _, _, _, f in tri)
            for hn, Q, G, f in tri:
                Oc = Q + fmax * (Vector((0.0, 0.0)) - Q)
                Gg = Q + f * (G - Q)
                poly = ccw([Q[:], Oc[:], Gg[:]])
                half = self.panels[hn]
                n_ = half.asm(tr).to_3x3() @ Z
                sg = 1.0 if n_.dot(up) >= 0 else -1.0

                def asm(t, f_=half.asm, sg=sg):
                    M = f_(t)
                    return Matrix.Translation(sg * TAB_LIFT * (M.to_3x3() @ Z).normalized()) @ M

                self.add(Panel(f"{piece}.{hn.split('.')[-1]}", piece, "panel", [poly], asm,
                               hn, None, f"{lab}: roof ledge"))
