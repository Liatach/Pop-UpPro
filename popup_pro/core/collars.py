"""Collars: balcony floors all the way round a tower (or a tapered top), their
sliding and curling corners, railings and tiers."""
import math

from mathutils import Matrix, Vector

from .base import Hinge, Host, Panel, poly_area
from .geom import Z, ccw, clip_halfplane, frame, hinge_frame_2d, v3


class Collars:
    """Collar builders. Mixed into Model (model.py)."""

    def _tower_collar(self, m, host, base, a, b, y0, w, tab):
        """Kim Lang's collar: a floor round a tower, part-way up or at its top,
        that still folds flat. Each side's floor is hinged on its wall (a
        strip glued down the wall) and slopes up and out (a balcony) or up
        and in, from the top (a tapered top). At the two corners that close as
        the card shuts the two floors meeting there are one V-fold hung on
        the corner, creased along the mitre; at the other two they only meet,
        a mm or two apart, and as it shuts one slides inside the other,
        curling its end out of the way. Any slope short of level works, the
        same both sides of each corner. A railing (battlements optional)
        stands on each floor's outer edge, upright like the walls."""
        lab = m["label"]
        tr = self.tmax
        S0, l0, r0, Y0, nl, nr = host.dirs(tr)
        top = y0 + w
        inward = m.get("collar_dir", "OUT") == "IN"
        below = min(max(0.0, float(m.get("collar_below", 0.0) or 0.0)), 0.9 * w)
        if inward:
            below = 0.0  # (a tapered top starts at the top)
        yv = top - below
        cw = max(2.0, float(m.get("collar_width", 8.0) or 8.0))
        if inward:
            cw = min(cw, 0.45 * min(a, b) / max(math.sin(math.radians(5.0)), 1e-6))
        beta = math.radians(min(max(float(m.get("collar_slope", 60.0)), 5.0), 80.0))
        if inward and cw * math.sin(beta) > 0.48 * min(a, b):
            cw = 0.48 * min(a, b) / math.sin(beta)
            self.warn(f"{lab}: a tapered top can only lean in half-way across the tower; "
                      f"made {cw:.1f} mm")
        if host.tower_top is not None and yv < host.tower_top - 1e-6:
            self.warn(f"{lab}: a collar goes on the tower above the castle's walls "
                      f"({host.tower_top - y0:.0f} mm up it at least); raised to that")
            yv = host.tower_top
        gap = 0.5 * max(0.0, float(m.get("collar_gap", 0.75)))
        S = S0 + yv * Y0
        A = S + a * l0
        B = S + b * r0
        C = A + b * r0
        S1, l1, r1, _, _, _ = host.dirs(max(2.0, 0.1 * tr))
        opening = l1.angle(r1) > l0.angle(r0)
        if any(n not in self.panels for n in self._tw_pair(base)):
            return
        ring = [S, A, C, B]
        corners = self._tower_vcorners(host, base, a, b, y0, lab, "collar", opening,
                                       S, A, B, C)
        rt = min(tab, 0.4 * w, max(2.0, yv - y0 - 1.0))
        if inward and opening:
            for tn in (f"{base}.TabA", f"{base}.TabB"):
                # the tower's tabs stop short of the taper's (both inside the walls)
                if tn in self.panels:
                    p_ = self.panels[tn]
                    p_.polys = [ccw(q) for q in (clip_halfplane(q, (0.0, -1.0),
                                                                -(w - rt - 1.0))
                                                 for q in p_.polys) if len(q) >= 3]
        rail_h = max(0.0, float(m.get("collar_rail", 0.0) or 0.0))
        tiers = max(1, int(m.get("collar_tiers", 1) or 1))
        if tiers > 1 and rail_h <= 0:
            self.warn(f"{lab}: collar tiers stand on railings; give it a railing")
            tiers = 1
        alt = bool(m.get("collar_alternate", False))
        if inward and tiers > 1 and not alt:
            # each tier leans in as far again: they meet in the middle
            fit = max(1, int(0.48 * min(a, b) / max(1e-6, cw * math.sin(beta)) + 1e-6))
            if tiers > fit:
                self.warn(f"{lab}: only {fit} tapered tier{'s' if fit > 1 else ''} fit "
                          f"before they meet in the middle (narrower floors fit more)")
                tiers = fit
        for tier in range(tiers):
            last = tier == tiers - 1
            if tier > 0:  # (its tabs glue down the railing below)
                rt = max(1.5, min(rt, rail_h - 0.5))
            inw = inward != (alt and tier % 2 == 1)  # (alternating: every other one turned)
            got = self._collar_tier(m, tier, ring, corners, Y0, inw, cw, beta, rt,
                                    yv if tier == 0 else rail_h, gap, rail_h, host, last,
                                    flip=not inw)
            short = got is None or (rail_h > 0 and len(got[1]) < 2)
            if short and tier > 0:
                self.warn(f"{lab}: only {tier} collar tier{'s' if tier > 1 else ''} fit "
                          f"(a tapered top meets in the middle); the rest left off")
                break
            if got is None or last:
                break
            Xo, rails = got
            # the next tier hangs on this one's railings: its ring their tops
            ring = [Xo[i] + rail_h * Y0 for i in range(4)]
            corners = self._rail_corners(lab, tier, ring, rails)
            if corners is None:
                self.warn(f"{lab}: only {tier + 1} collar tier{'s' if tier else ''} fit; "
                          f"the rest left off")
                break

    def _rail_corners(self, lab, tier, ring, rails):
        """The corners of a ring of collar railings that close as the card
        shuts (where the floors below were one V-fold): Hosts on the two
        railings meeting there, virtual x along each away from the corner,
        y up it from its foot."""
        out = []
        for (iX, iL, iR), (rl, rr) in rails.items():
            if rl is None or rr is None:
                return None
            Ts = []
            for (rn, q0, d, nrm), sx in ((rl, -1.0), (rr, 1.0)):
                c0 = Vector((sx * d.x, sx * d.y, 0.0))
                c1 = Vector((nrm.x, nrm.y, 0.0))
                c2 = c0.cross(c1).normalized()
                T = Matrix.Identity(4)
                for r_ in range(3):
                    T[r_][0], T[r_][1], T[r_][2] = c0[r_], c1[r_], c2[r_]
                T[0][3], T[1][3] = q0.x, q0.y
                Ts.append(T)
            hc = Host(self, rl[0], 0.0, 0.0, rr[0], 0.0, 0.0,
                      f"{lab}: collar tier {tier + 2} corner", Ts[0], Ts[1])
            out.append((hc, ring[iX], ring[iL], ring[iR]))
        return out

    def _collar_tier(self, m, tier, ring, corners, Y0, inward, cw, beta, rt, yv, gap,
                     rail_h, host, last, flip=True):
        """One tier of a collar round a ring of four walls (a tower's, or the
        railings of the tier below): floors hinged on the walls at virtual
        height yv, V-folds at the closing corners, the free corners sliding
        inside and curling, railings. Returns the floors' outer corners and
        the railings (for the next tier)."""
        uid, lab = m["uid"], m["label"]
        tr = self.tmax
        mid = sum(ring, Vector()) / 4.0
        sgn = -1.0 if inward else 1.0

        def out_of(P, Q):  # the floor's way up and out (or in) from wall P-Q
            d = (Q - P).normalized()
            n = d.cross(Y0).normalized()
            if n.dot(0.5 * (P + Q) - mid) * sgn < 0:
                n = -n
            return n, (math.cos(beta) * Y0 + math.sin(beta) * n).normalized()

        def outer(X, P, Q):
            """Where the floors' outer edges meet above corner X (walls X-P,
            X-Q)."""
            n1, _ = out_of(X, P)
            n2, _ = out_of(X, Q)
            off = cw * math.sin(beta)
            d1, d2 = (P - X).normalized(), (Q - X).normalized()
            M_ = Matrix(((d1.dot(d1), -d1.dot(d2)), (d1.dot(d2), -d2.dot(d2))))
            rhs = Vector(((off * (n2 - n1)).dot(d1), (off * (n2 - n1)).dot(d2)))
            try:
                st_ = M_.inverted() @ rhs
            except ValueError:
                return X + off * n1 + cw * math.cos(beta) * Y0
            return X + off * n1 + st_[0] * d1 + cw * math.cos(beta) * Y0

        Xo = {i: outer(X, ring[i - 1], ring[(i + 1) % 4]) for i, X in enumerate(ring)}
        floors = []  # (half, free corner index, its pattern: X, P, P', Xc)
        sides = {}  # corner (iX, iL, iR) -> its two floors
        tag = f"{uid}c" if tier == 0 else f"{uid}t{tier}c"
        for k, (hc, X, PL, PR) in enumerate(corners):
            hc.finish()
            if flip:
                hc.lift = (-hc.lift[0], -hc.lift[1])  # (its tabs glue outside the walls)
            hc.trig = False
            iX = next(i for i, P in enumerate(ring) if (P - X).length < 1e-6)
            iL = next(i for i, P in enumerate(ring) if (P - PL).length < 1e-6)
            iR = next(i for i, P in enumerate(ring) if (P - PR).length < 1e-6)
            Xc = Xo[iX]
            gl, gr = (PL - X).length, (PR - X).length
            al = math.degrees((PL - X).angle(Xc - X))
            ar = math.degrees((PR - X).angle(Xc - X))
            n0 = len(self.order)
            self._vfold(dict(uid=f"{tag}{k}", type="VFOLD", label=f"{lab} collar",
                             y=yv, phi_l=90.0, phi_r=90.0, alpha_l=al, alpha_r=ar,
                             glue=gl, glue_r=gr, height=(Xc - X).length, tab=rt,
                             shape="QUAD", tab_side="OUT", pref=(0.0, 1.0),
                             slot=(880 + 2 * uid + k + 40 * tier) % 1000), hc)
            for name in self.order[n0:]:
                hg = self.panels[name].hinge
                if hg is not None and hg.kind in ("LINEAR", "SPHERICAL", "EXPR"):
                    hg.kind = "TABLE"
                if hg is not None:
                    hg.host_bound = True
            # each half: the floor of one side, from the V-fold's corner to the
            # free corner, cut along both mitres
            for side, P_, iP in (("HalfL", PL, iL), ("HalfR", PR, iR)):
                hn = next((n for n in self.order[n0:] if n.endswith("." + side)), None)
                if hn is None:
                    continue
                half = self.panels[hn]
                Mi = half.asm(tr).inverted()
                poly = [(Mi @ q).to_2d()[:] for q in (X, P_, Xo[iP], Xc)]
                half.polys = [ccw(poly)]
                floors.append((hn, iP, [Vector(q) for q in poly]))
                sides.setdefault((iX, iL, iR), {})[side] = hn
                # its tab: a strip glued down the wall, the length of its hinge
                tn = hn[:-len(side)] + ("TabL" if side == "HalfL" else "TabR")
                if tn in self.panels:
                    O_, G_ = Vector(poly[0]), Vector(poly[1])
                    d = (G_ - O_).normalized()
                    nrm = Vector((-d.y, d.x))
                    c_ = sum((Vector(q) for q in poly), Vector((0.0, 0.0))) / len(poly)
                    if (c_ - O_).dot(nrm) > 0:
                        nrm = -nrm  # (away from the floor)
                    L_ = (G_ - O_).length
                    ch = min(0.3 * rt, 0.2 * L_)
                    tab_ = [O_, G_, G_ + nrm * rt - d * ch, O_ + nrm * rt + d * ch]
                    # (the two tabs meet under the crease, x = 0: each keeps its side)
                    sx = 1.0 if c_.x >= 0 else -1.0
                    tab_ = clip_halfplane([q[:] for q in tab_], (sx, 0.0), 0.3)
                    # on a railing that stops short (where the floor below
                    # curls), only as long as the railing
                    lim = self._rail_len.get(hc.p1 if side == "HalfL" else hc.p2)
                    if len(tab_) >= 3:  # (not back past the corner)
                        tab_ = clip_halfplane(tab_, (d.x, d.y), d.dot(O_) + 0.2)
                    if lim is not None and lim < L_ - 0.05 and len(tab_) >= 3:
                        tab_ = clip_halfplane(tab_, (-d.x, -d.y),
                                              -(d.dot(O_) + lim - 0.3))
                    if len(tab_) >= 3:
                        self.panels[tn].polys = [ccw(tab_)]
        if tier > 0:
            # its tabs glue on the railings below: trimmed to fit on them
            for hc, X, PL, PR in corners:
                for rn in (hc.p1, hc.p2):
                    for tn in [n for n in self.order if self.panels[n].parent == rn and
                               self.panels[n].kind == "tab" and n.startswith(f"VFold{tag}")]:
                        tp, rp_ = self.panels[tn], self.panels[rn]
                        M = rp_.asm(tr).inverted() @ tp.asm(tr)
                        Mi = M.inverted()
                        q = [(M @ v3(c)).to_2d()[:] for c in tp.polys[0]]
                        box = ccw(rp_.polys[0])
                        for i in range(len(box)):
                            (x0, y0_), (x1, y1) = box[i], box[(i + 1) % len(box)]
                            n_ = Vector((-(y1 - y0_), x1 - x0)).normalized()
                            if len(q) >= 3:
                                q = clip_halfplane(q, (n_.x, n_.y),
                                                   n_.dot(Vector((x0, y0_))) + 0.2)
                        if len(q) >= 3 and abs(poly_area(q)) > 1.0:
                            tp.polys = [ccw([(Mi @ v3(c)).to_2d()[:] for c in q])]
        if tier == 0:
            self.collar_free[uid] = [(hn, iP) for hn, iP, _ in floors]
        # the free corners: the floors stop a mm or two short of each other on
        # the mitre; as it shuts each would pass through the other along a
        # line turning about the tower's corner, so one slides inside the other
        # (towards the tower), its end curling out of the way, or is cut back
        style = m.get("collar_corner", "SLIDE")
        if style not in ("SLIDE", "NOTCH"):
            style = "SLIDE"
        for hn, iP, pp in floors:
            half = self.panels[hn]
            X_, P_, Pp, Xc_ = pp
            # back from the mitre (P - P') by half the gap
            d = (Pp - P_).normalized()
            nrm = Vector((-d.y, d.x))
            if (X_ - P_).dot(nrm) < 0:
                nrm = -nrm
            half.polys = [ccw(clip_halfplane(half.polys[0], (nrm.x, nrm.y),
                                             nrm.dot(P_) + gap))]
        curls = {}
        for iP in sorted({i for _, i, _ in floors}):
            pair = [hn for hn, i, _ in floors if i == iP]
            if len(pair) != 2:
                continue
            na, nb = pair  # na slides inside nb
            pa, pb = self.panels[na], self.panels[nb]
            line = self._cut_line(pa, pb, max(1.0, 0.02 * tr))
            if line is None:
                continue
            P_ = Vector((pa.asm(tr).inverted() @ ring[iP]).to_2d())
            E = max(line, key=lambda q: (q - P_).length)  # on the outer edge
            keep = self._side_of(P_, E, pa.polys[0])
            main = clip_halfplane(pa.polys[0], *keep)
            flap = clip_halfplane(pa.polys[0], (-keep[0][0], -keep[0][1]), -keep[1])
            if len(main) >= 3:
                pa.polys = [ccw(main)]
            if style == "NOTCH" or len(flap) < 3 or abs(poly_area(flap)) < 0.2:
                continue
            curls[na] = (P_, E)
            # the curl: the end beyond P-E turns about it, towards the tower,
            # just as far as it must to stay inside the other floor
            ax = (E - P_).normalized()
            Pi = frame(Vector((P_.x, P_.y, 0.0)), (ax.x, ax.y, 0.0), (-ax.y, ax.x, 0.0))
            Pinv = Pi.inverted()
            # points over the flap (where it might meet the other floor)
            fl3 = []
            cx = sum(q[0] for q in flap) / len(flap)
            cy = sum(q[1] for q in flap) / len(flap)
            for q in flap:
                for f_ in (1.0, 0.66, 0.33):
                    fl3.append(Vector((cx + f_ * (q[0] - cx), cy + f_ * (q[1] - cy), 0.0)))
            for i in range(len(flap)):
                q, r_ = flap[i], flap[(i + 1) % len(flap)]
                for f_ in (0.25, 0.5, 0.75):
                    fl3.append(Vector((q[0] + f_ * (r_[0] - q[0]), q[1] + f_ * (r_[1] - q[1]),
                                       0.0)))
            pbp = ccw(pb.polys[0])
            cache = {}
            # the side of the other floor the curl stays on: the side its own
            # floor is on, just short of the seam
            sm = 0.5 * (P_ + E) + Vector((keep[0][0], keep[0][1])) * 2.0
            seam_in = Vector((sm.x, sm.y, 0.0))

            # the flap's points off the seam itself (on it, it can't move)
            fl3 = [q for q in fl3 if abs((Pinv @ q).y) > 0.6] or fl3
            seam3 = [Vector((P_.x + f_ * (E.x - P_.x), P_.y + f_ * (E.y - P_.y), 0.0))
                     for f_ in (0.0, 0.25, 0.5, 0.75, 1.0)]

            def turn(t, sg, pa=pa, pb=pb, Pi=Pi, Pinv=Pinv, fl3=fl3, cache=cache, pbp=pbp,
                     seam_in=seam_in, seam3=seam3):
                """How far (radians, turning way sg) the end must curl at
                opening t to keep clear of the other floor: 0 if it needn't,
                None if it can't."""
                k_ = (float(t), sg)
                if k_ in cache:
                    return cache[k_]
                Ma, Mb = pa.asm(t), pb.asm(t)
                Mbi = Mb.inverted()
                o, nb_ = Mb.translation, (Mb.to_3x3() @ Z).normalized()
                if ((Ma @ seam_in) - o).dot(nb_) > 0:
                    nb_ = -nb_  # (nb_ points away from this floor's side)

                def over_b(q3):  # over (or under) the other floor, not past its edge
                    u = Mbi @ q3
                    for i in range(len(pbp)):
                        x0, y0_ = pbp[i]
                        x1, y1 = pbp[(i + 1) % len(pbp)]
                        if (x1 - x0) * (u.y - y0_) - (y1 - y0_) * (u.x - x0) < -0.5:
                            return False
                    return True

                # the clearance it keeps: 0.3 mm, or less where the floors
                # themselves come closer than that at the seam (nearly shut)
                dz = [-((Ma @ q) - o).dot(nb_) for q in seam3 if over_b(Ma @ q)]
                need = min(0.3, max(0.02, 0.6 * min(dz))) if dz else 0.3

                def worst(th):
                    R = Pi @ Matrix.Rotation(th, 4, "X") @ Pinv
                    w_ = -1e9
                    for q in fl3:
                        q3 = Ma @ R @ q
                        if over_b(q3):
                            w_ = max(w_, (q3 - o).dot(nb_))
                    return w_

                best = 0.0
                if worst(0.0) > -need:
                    lo_, hi_, best = 0.0, None, None
                    for deg in (40.0, 80.0, 120.0, 160.0):
                        if worst(sg * math.radians(deg)) <= -need:
                            hi_ = sg * math.radians(deg)
                            break
                        lo_ = sg * math.radians(deg)
                    if hi_ is not None:
                        for _ in range(30):
                            md = 0.5 * (lo_ + hi_)
                            if worst(md) > -need:
                                lo_ = md
                            else:
                                hi_ = md
                        best = hi_
                cache[k_] = best
                return best

            tg = [tr * i / 72.0 for i in range(73)]
            env = {}

            def curl(t, turn=turn, tg=tg, env=env, Pi=Pi, Pinv=Pinv):
                """How far it's curled: as far as it must be at each opening
                (always the same way), easing back flat as the card shuts
                rather than springing straight back."""
                if "raw" not in env:
                    # the way that works most of the way (towards the tower)
                    got = {}
                    for sg in (1.0, -1.0):
                        rs = [turn(x, sg) for x in tg]
                        got[sg] = (sum(r_ is None for r_ in rs),
                                   sum(abs(r_) for r_ in rs if r_ is not None), rs)
                    sg = min(got, key=lambda k: got[k][:2])
                    rs = got[sg][2]
                    # (where it can't keep clear, as far as it got either side)
                    for i, r_ in enumerate(rs):
                        if r_ is None:
                            nb2 = [abs(x) for x in rs[max(0, i - 3):i + 4] if x is not None]
                            rs[i] = sg * max(nb2 + [math.radians(160.0) if not nb2 else 0.0])
                    env["raw"] = [abs(r_) for r_ in rs]
                    env["sg"] = sg
                raw, sg = env["raw"], env["sg"]
                W, step = 30.0, tg[1] - tg[0]
                t_ = max(0.0, min(tg[-1], float(t)))
                i = min(len(tg) - 2, int(t_ / step))
                f_ = (t_ - tg[i]) / step
                best = raw[i] + f_ * (raw[i + 1] - raw[i])  # (as far as it must)
                for x, r_ in zip(tg[i + 1:], raw[i + 1:]):
                    if x - t_ >= W:
                        break
                    best = max(best, r_ * (1.0 - (x - t_) / W))
                best *= min(1.0, t_ / 3.0)  # (flat when shut)
                return Pi @ Matrix.Rotation(sg * best, 4, "X") @ Pinv

            def asm_f(t, pa=pa, curl=curl):
                return pa.asm(t) @ curl(t)

            hf = hinge_frame_2d((P_.x, P_.y), (ax.x, ax.y))
            fp = self.add(Panel(f"{na}Curl", pa.piece, "panel", [ccw(flap)], asm_f, na,
                                Hinge(hf, hf, "TABLE", {}), f"{lab}: collar corner"))
            fp.hinge.host_bound = True
            fp.hinge.kink_ok = True  # (it starts turning when the floors touch)
            pr = frozenset((na, fp.name))
            self.fold_kind[pr] = "skip"  # (it curls, it isn't creased)
            self.facets.add(pr)
            self.smooth_panels.update((na, fp.name))
        rails = {}
        if rail_h > 0:
            rails = self._collar_rails(m, floors, curls, rail_h, host, last)
        out = {}
        for key, hs in sides.items():
            out[key] = (rails.get(hs.get("HalfL")), rails.get(hs.get("HalfR")))
        return Xo, out

    def _collar_rails(self, m, floors, curls, rh, host, last=True):
        """A railing on each collar floor's outer edge, standing upright (like
        the walls) as the floor turns, so it folds flat on it; on a floor
        whose end curls it carries on along the curl, meeting its own part
        on an upright line where the curl starts, so it runs right into the
        corner. Battlements cut along the top tier's if asked. Returns each
        floor's railing (name, start, way along, way up, in its pattern)."""
        lab = m["label"]
        cren = bool(m.get("collar_crenels", False)) and last
        out = {}
        for hn, iP, pp in floors:
            half = self.panels[hn]
            poly = half.polys[0]
            X_, P_, Pp, Xc_ = pp
            # the outer edge as it stands after trimming: from Xc to wherever
            # it now meets the free end (or the curl's seam)
            d = (Pp - Xc_).normalized()
            nrm = Vector((-d.y, d.x))
            if (X_ - Xc_).dot(nrm) > 0:
                nrm = -nrm  # (outwards, away from the floor)
            on = [Vector(q) for q in poly if abs((Vector(q) - Xc_).dot(nrm)) < 1e-4]
            if len(on) < 2:
                continue
            q0 = min(on, key=lambda q: (q - Xc_).dot(d))
            q1 = max(on, key=lambda q: (q - Xc_).dot(d))
            L_ = (q1 - q0).length
            if L_ < 1.0:
                continue
            # pattern: x along the edge from q0, y out from it (up the railing)
            to_pat = lambda u, v, q0=q0, d=d, nrm=nrm: q0 + d * u + nrm * v  # noqa: E731

            def parts(u0, u1):
                L1 = u1 - u0
                if cren and rh >= 4.0 and L1 > 2.0:
                    n_ = max(1, int(round(L1 / 5.0)))
                    n_ += 1 - n_ % 2
                    seg, dep = L1 / n_, min(0.4 * rh, 3.0)
                    ps = [[(u0, 0.0), (u1, 0.0), (u1, rh - dep), (u0, rh - dep)]] + \
                        [[(u0 + i * seg, rh - dep), (u0 + (i + 1) * seg, rh - dep),
                          (u0 + (i + 1) * seg, rh), (u0 + i * seg, rh)]
                         for i in range(0, n_, 2)]
                else:
                    ps = [[(u0, 0.0), (u1, 0.0), (u1, rh), (u0, rh)]]
                return [ccw([to_pat(u, v)[:] for u, v in q]) for q in ps]

            def make_asm(pan, q0=q0, d=d, nrm=nrm):
                def asm(t):
                    M = pan.asm(t)
                    o = M @ v3(q0)
                    e = (M.to_3x3() @ Vector((d.x, d.y, 0.0))).normalized()
                    S_, l_, r_, Y_, _, _ = host.dirs(t)
                    up = Y_ - Y_.dot(e) * e
                    Fp = frame(Vector((q0.x, q0.y, 0.0)), (d.x, d.y, 0.0),
                               (nrm.x, nrm.y, 0.0))
                    return frame(o, e, up) @ Fp.inverted()
                return asm

            hf = hinge_frame_2d((q0.x, q0.y), (d.x, d.y))
            rp = self.add(Panel(f"{hn}Rail", half.piece, "panel", parts(0.0, L_),
                                make_asm(half), hn, Hinge(hf, hf, "TABLE", {}),
                                f"{lab}: collar railing"))
            rp.hinge.host_bound = True
            out[hn] = (rp.name, q0, d, nrm)
            self._rail_len[rp.name] = L_
            cn = f"{hn}Curl"
            if cn in self.panels:
                # on along the curl, from where it starts to the corner
                cp = self.panels[cn]
                onc = [Vector(q) for q in cp.polys[0]
                       if abs((Vector(q) - Xc_).dot(nrm)) < 1e-4]
                if len(onc) >= 2:
                    u1 = max((q - q0).dot(d) for q in onc)
                    if u1 > L_ + 0.5:
                        rc = self.add(Panel(f"{cn}Rail", half.piece, "panel",
                                            parts(L_, u1), make_asm(cp), cn,
                                            Hinge(hf, hf, "TABLE", {}),
                                            f"{lab}: collar railing"))
                        rc.hinge.host_bound = True
                        rc.hinge.kink_ok = True
                        pr = frozenset((rp.name, rc.name))
                        self.fold_kind[pr] = "skip"  # (one strip, bending there)
        return out
