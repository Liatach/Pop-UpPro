"""Tethers: walls from a tube's corner or crease to another tube or to a foot
on a strip."""
import math

from mathutils import Vector

from .base import Hinge, Panel, Piece, T_MIN, TAB_LIFT
from .geom import Z, frame, hinge_frame_2d


class Tethers:
    """Tether builders. Mixed into Model (model.py)."""

    def _tether(self, m):
        """Wall joining a tube's corner or crease to another tube's, or to a
        small foot glued on a strip. Straight if its ends stay the same
        distance apart; otherwise it gets a vertical crease and is long
        enough for the farthest the ends get apart (plus Slack)."""
        uid, lab = m["uid"], m["label"]
        A_uid, A_pt = int(m["from_uid"]), m.get("from_pt", "FL")
        TA = self.tubes.get(A_uid)
        if TA is None:
            self.warn(f"{lab}: its tube was skipped; skipped too")
            return
        host, a = TA["host"], TA["a"]
        to = m.get("to", "LEFT")
        hgt = float(m.get("height", TA["h"]))
        tb = min(float(m.get("tab", 10.0)), 20.0)
        kf = float(m.get("foot", 12.0))
        piece = f"Tether{uid}"
        self.add_piece(Piece(piece, lab, 1 + uid, (40.0, 0.5 * hgt)))

        if to == "TUBE":
            TB = self.tubes.get(int(m["to_uid"]))
            if TB is None:
                self.warn(f"{lab}: its second tube was skipped; skipped too")
                return
            if abs(TB["a"] - a) > 1e-6:
                self.warn(f"{lab}: joined tubes must use the same Strip Distance (the walls "
                          f"would have to slide); skipped")
                return
            B_uid, B_pt = int(m["to_uid"]), m.get("to_pt", "FR")

            def endB(t):
                return self.tube_plan(B_uid, t)[B_pt]
        else:
            sgnx = -1.0 if to == "LEFT" else 1.0
            yb = float(m.get("to_y", 100.0))

            def endB(t):
                S, e, xh, Y, sn, cs = self.strip_frame(host, t)
                return (sgnx * a * sn, yb)

        def endA(t):
            return self.tube_plan(A_uid, t)[A_pt]

        def dist(t):
            pa, pb = endA(t), endB(t)
            return math.hypot(pb[0] - pa[0], pb[1] - pa[1])

        ds = [dist(t) for t in self.TABLE_T]
        dmin, dmax, d0 = min(ds), max(ds), ds[0]
        if dmax < 1.0:
            self.warn(f"{lab}: its ends meet; skipped")
            return

        # ends may meet as the card shuts (like a tube's own front pair), but
        # must not run into each other part way open
        dips = [ds[i] for i in range(1, len(ds) - 1)
                if ds[i] <= ds[i - 1] and ds[i] <= ds[i + 1] and self.TABLE_T[i] > 1.0]
        if dips and min(dips) < 2.0:
            self.warn(f"{lab}: its two ends pass through each other as the card opens; "
                      f"skipped (join points that stay apart)")
            return
        straight = dmax - dmin < 0.05 and float(m.get("slack", 0.0)) <= 0.0
        # A creased tether has to lie flat when the card shuts, so its halves
        # differ by exactly the closed distance between its ends (it folds
        # back on itself there), and together reach the farthest the ends get
        # apart, plus slack (half a millimetre at least, or it binds).
        L = dmax + (0.0 if straight else max(float(m.get("slack", 0.0)), 0.5))

        def lead_dir():
            # direction the ends approach each other from as the card shuts
            for tt in (2.0, 5.0, 10.0, 30.0, 90.0):
                pa, pb = endA(tt), endB(tt)
                dd = math.hypot(pb[0] - pa[0], pb[1] - pa[1])
                if dd > 0.05:
                    return ((pb[0] - pa[0]) / dd, (pb[1] - pa[1]) / dd)
            return (1.0, 0.0)

        u_near = lead_dir()
        if not straight and d0 < 0.5:
            # The ends meet as the card shuts. That folds flat only if they
            # come together across the fold (like a tube's front pair: the
            # crease then lies along the fold); head-on along it, the tether
            # would have to snap over.
            if abs(u_near[0]) < 0.7:
                self.warn(f"{lab}: its ends meet head-on along the fold as the card shuts, "
                          f"so it can't fold flat; move one end")
                return
            d0 = 0.0
        if not straight and dmin < d0 - 0.3:
            self.warn(f"{lab}: its ends come closer together as the card starts to open than "
                      f"when it is shut, so it can't both fold flat and reach; move one end")
            return
        d0 = min(d0, dmin)
        # When shut it folds back on itself past one end; pick the end that
        # keeps that fold on the card (nearest the middle).
        pa0, _pb0 = endA(T_MIN), endB(T_MIN)
        past = []
        for longA in (True, False):
            la, lb = (0.5 * (L + d0), 0.5 * (L - d0)) if longA else (0.5 * (L - d0), 0.5 * (L + d0))
            ux, uy = u_near
            cy = pa0[1] + (la if longA else -la) * uy
            past.append((abs(cy - 0.5 * self.H), la, lb))
        _, L1, L2 = min(past)

        def crease(t, side):
            pa, pb = endA(t), endB(t)
            dx, dy = pb[0] - pa[0], pb[1] - pa[1]
            d = math.hypot(dx, dy)
            if d < 0.05:  # ends (nearly) together: use the way they approach
                ux, uy = u_near
                d = max(d, 1e-9)
            else:
                ux, uy = dx / d, dy / d
            ca = max(-1.0, min(1.0, (L1 * L1 + d * d - L2 * L2) / (2 * L1 * d)))
            sa = math.sqrt(1 - ca * ca) * side
            return (pa[0] + L1 * (ca * ux - sa * uy), pa[1] + L1 * (ca * uy + sa * ux))

        def poke(side):
            worst = 0.0
            for t in self.TABLE_T[::5]:
                S, e, xh, Y, sn, cs = self.strip_frame(host, t)
                worst = max(worst, abs(crease(t, side)[0]) - a * sn)
            return worst

        bend = m.get("bend", "AUTO")
        if straight:
            side = 1.0
        elif bend == "AUTO":
            side = min((1.0, -1.0), key=poke)
        else:
            want = -1.0 if bend == "FRONT" else 1.0  # front = towards smaller y
            side = max((1.0, -1.0), key=lambda sd: want * (crease(90.0, sd)[1] -
                                                           0.5 * (endA(90.0)[1] + endB(90.0)[1])))
        if not straight and poke(side) > 0.5:
            self.warn(f"{lab}: its crease swings outside the strips, so it would pass under "
                      f"the pages; try the other Bend or move its ends")

        def plan(t):
            out = dict(A=endA(t), B=endB(t))
            if not straight:
                out["C"] = crease(t, side)
            return out

        if straight:
            segs = [("W1", "A", "B", 0.0, dmax)]
        else:
            segs = [("W1", "A", "C", 0.0, L1), ("W2", "C", "B", L1, L1 + L2)]
        Ltot = segs[-1][4]
        att_wall, att_toward = TA["attach"][A_pt]
        prev = None
        for i, (nm, p0, p1, u0, u1) in enumerate(segs):
            poly = [(u0, 0), (u1, 0), (u1, hgt), (u0, hgt)]
            asm = self._wall_asm(host, a, p0, p1, u0, plan)
            parent = att_wall if prev is None else prev.name
            if prev is None:
                # hinge on the tube wall's vertical edge at point A
                Tu = self._tube_u(A_uid, A_pt, att_wall)
                Hp = hinge_frame_2d((Tu, 0), (0, 1))
            else:
                Hp = hinge_frame_2d((u0, 0), (0, 1))
            prev = self.add(Panel(f"{piece}.{nm}", piece, "panel", [poly], asm, parent,
                                  Hinge(Hp, hinge_frame_2d((u0, 0), (0, 1)), "TABLE", {}),
                                  f"{lab}: wall {i + 1}"))
        # glue tab at A, on the outside of the tube wall
        A_wall_other = att_toward

        def asm_tabA(t):
            p = self.tube_plan(A_uid, t)
            S, e, xh, Y, sn, cs = self.strip_frame(host, t)
            a3 = self.plan3d(host, a, t, p[A_pt])
            o3 = self.plan3d(host, a, t, p[A_wall_other])
            Mw = self.panels[att_wall].asm(t)
            nout = Mw.to_3x3() @ Z
            return frame(a3 + TAB_LIFT * nout, (a3 - o3).normalized(), e)

        tabA = [(-tb, min(0.2 * hgt, 0.3 * tb)), (0, 0), (0, hgt), (-tb, hgt - min(0.2 * hgt, 0.3 * tb))]
        self.add(Panel(f"{piece}.TabA", piece, "tab", [tabA], asm_tabA, att_wall, None,
                       f"{lab}: glue tab"))
        if to == "TUBE":
            Bw, Btoward = self.tubes[int(m["to_uid"])]["attach"][m.get("to_pt", "FR")]
            B_uid_, B_pt_ = int(m["to_uid"]), m.get("to_pt", "FR")

            def asm_tabB(t):
                p = self.tube_plan(B_uid_, t)
                b3 = self.plan3d(host, a, t, p[B_pt_])
                o3 = self.plan3d(host, a, t, p[Btoward])
                S, e, xh, Y, sn, cs = self.strip_frame(host, t)
                nout = self.panels[Bw].asm(t).to_3x3() @ Z
                return frame(b3 + TAB_LIFT * nout, (o3 - b3).normalized(), e) \
                    @ frame(Vector((Ltot, 0, 0)), (1, 0, 0), (0, 1, 0)).inverted()

            tabB = [(Ltot, 0), (Ltot + tb, min(0.2 * hgt, 0.3 * tb)),
                    (Ltot + tb, hgt - min(0.2 * hgt, 0.3 * tb)), (Ltot, hgt)]
            self.add(Panel(f"{piece}.TabB", piece, "tab", [tabB], asm_tabB, Bw, None,
                           f"{lab}: glue tab"))
        else:
            # a short foot standing on the strip, glued down by a base tab
            yb = float(m.get("to_y", 100.0))
            last = self.panels[f"{piece}.{segs[-1][0]}"]
            pA0 = endA(180.0)
            fdir = 1.0 if yb >= pA0[1] else -1.0  # foot runs on away from the tube

            def foot_pts(t):
                pb = endB(t)
                return dict(B=pb, E=(pb[0], pb[1] + fdir * kf))

            fasm = self._wall_asm(host, a, "B", "E", Ltot, foot_pts)
            sgnx = -1.0 if to == "LEFT" else 1.0
            pg, Tp = (host.p1, host.T1) if to == "LEFT" else (host.p2, host.T2)
            foot = self.add(Panel(f"{piece}.Foot", piece, "panel",
                                  [[(Ltot, 0), (Ltot + kf, 0), (Ltot + kf, hgt), (Ltot, hgt)]],
                                  fasm, pg,
                                  Hinge(Tp @ hinge_frame_2d((sgnx * a, yb), (0, fdir)),
                                        hinge_frame_2d((Ltot, 0), (1, 0))),
                                  f"{lab}: foot"))
            # re-parent the last wall onto the foot: the chain is page -> foot -> walls
            last.parent = foot.name
            last.hinge = Hinge(hinge_frame_2d((Ltot, 0), (0, 1)),
                               hinge_frame_2d((Ltot, 0), (0, 1)), "TABLE", {})
            # base tab under the foot, folded away from the tether
            kk = 1.0 if m.get("tab_side", "IN") == "IN" else -1.0
            # strip pattern +v -> across the strip, so the tab (v < 0) folds
            # towards the fold for IN, away for OUT
            T = frame(Vector((sgnx * a, yb, TAB_LIFT)), (0, fdir, 0), (sgnx * kk, 0, 0)) \
                @ frame(Vector((Ltot, 0, 0)), (1, 0, 0), (0, 1, 0)).inverted()
            c2 = min(0.3 * tb, 0.2 * kf)
            poly = [(Ltot + c2, -tb), (Ltot, 0), (Ltot + kf, 0), (Ltot + kf - c2, -tb)]
            pa_ = self.panels[pg].asm
            Tpat = Tp @ T
            self.add(Panel(f"{piece}.FootTab", piece, "tab", [poly],
                           (lambda t, pa=pa_, T=Tpat: pa(t) @ T), pg, None, f"{lab}: foot tab"))
            # the chain must be parent-first: move the walls after the foot
            for nm, *_ in segs[::-1]:
                n_ = f"{piece}.{nm}"
                self.order.remove(n_)
                self.order.insert(self.order.index(foot.name) + 1, n_)
            # walls now hang from the foot: W2 <- foot, W1 <- W2
            if not straight:
                w1 = self.panels[f"{piece}.W1"]
                w1.parent = last.name
                w1.hinge = Hinge(hinge_frame_2d((L1, 0), (0, 1)), hinge_frame_2d((L1, 0), (0, 1)),
                                 "TABLE", {})
                self.order.remove(w1.name)
                self.order.insert(self.order.index(last.name) + 1, w1.name)
        self.tethers[uid] = dict(straight=straight, length=L)

    def _tube_u(self, uid, pt, wall):
        """Pattern u of a tube point on the given tube wall."""
        short = wall.split(".")[-1]
        pn, u0, u1, pk, qk = self.tubes[uid]["walls"][short]
        return u0 if pt == pk else u1
