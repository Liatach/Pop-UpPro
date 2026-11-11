"""Pull-tab flaps."""
import math

from mathutils import Matrix, Vector

from .base import Hinge, Panel, Piece, TAB_LIFT
from .geom import Z, frame, hinge_frame_2d


class Flaps:
    """Flap builders. Mixed into Model (model.py)."""

    # ------------------------------------------------------------------ flap
    def _flap(self, m):
        """Pull-tab flap on a page. The flap is glued down along its hinge by a
        tab. A strip glued under the flap runs back through a slit in the page
        and under it to the card edge; pulling it shortens the part above
        the page, which lifts the flap; it swings over towards the pull."""
        uid, lab = m["uid"], m["label"]
        W, H = self.W, self.H
        left = m.get("side", "R") == "L"
        page = "Page.L" if left else "Page.R"
        hx = -float(m["x"]) if left else float(m["x"])
        hy = float(m["y"])
        uu = {"TOP": (0, -1), "BOTTOM": (0, 1), "LEFT": (1, 0), "RIGHT": (-1, 0)}[m.get("hinge", "TOP")]
        U = Vector((uu[0], uu[1], 0))
        Hd = Z.cross(U)
        Wf, Lf = float(m["width"]), float(m["length"])
        # x, y is where the hinge starts; it runs Width from there: away from
        # the spine (a hinge across the page) or up the card (one along it)
        along = (Vector(((-1.0 if left else 1.0), 0.0, 0.0)) if uu[1] != 0
                 else Vector((0.0, 1.0, 0.0)))
        hx, hy = hx + 0.5 * Wf * along.x, hy + 0.5 * Wf * along.y
        tb = min(float(m.get("tab", 10.0)), 30.0)
        amax = float(m.get("angle", 150.0))
        ws = min(float(m.get("strip", 10.0)), Wf - 2)
        g = max(3.0, min(float(m.get("glue_at", 0.5 * Lf)), Lf - 2))
        gap = float(m.get("gap", 4.0))
        sl = tb + gap  # slit distance behind the hinge
        gl = min(10.0, Lf - g + 0.0, 0.5 * g) if Lf - g > 1 else 1.0
        pdir = -U  # the flap swings over towards the pull
        H3 = Vector((hx, hy, 0.0))
        S3 = H3 - sl * U

        def on_page(pt):
            x0, x1 = (-W, 0.0) if left else (0.0, W)
            return x0 - 1e-6 <= pt.x <= x1 + 1e-6 and -1e-6 <= pt.y <= H + 1e-6

        corners = [H3 + a * U + b * Hd for a in (-tb, Lf) for b in (-Wf / 2, Wf / 2)]
        if not all(on_page(c) for c in corners):
            self.warn(f"{lab}: the flap runs off its page")
        # distance from the slit to the page edge along the pull direction
        x0, x1 = (-W, 0.0) if left else (0.0, W)
        dists = []
        for axis, lo, hi in ((0, x0, x1), (1, 0.0, H)):
            dv = pdir[axis]
            if abs(dv) > 1e-9:
                for edge in (lo, hi):
                    tt = (edge - S3[axis]) / dv
                    if tt > 0:
                        dists.append((tt, axis, edge))
        if not dists:  # the slit is off the page already
            self.warn(f"{lab}: its pull slit lands off the page; skipped")
            return
        tt, axis, edge = min(dists)
        if axis == 0 and abs(edge) < 1e-9:
            self.warn(f"{lab}: the pull strip would run across the spine; turn the flap "
                      f"or swap Pull so it exits an outer edge")
        out = float(m.get("pull_out", 30.0))
        Lu = tt + out
        A = math.radians(amax)

        pf, ps = f"Flap{uid}", f"Pull{uid}"
        self.add_piece(Piece(pf, lab, 1 + uid, (0.5 * Lf, 0.0)))
        self.add_piece(Piece(ps, f"{lab} strip", 500 + uid, (0.5 * Lu, 0.0)))
        self.pull.setdefault(uid, 0.0)
        pa = self.panels[page].asm

        def theta():
            return A * max(0.0, min(1.0, self.pull.get(uid, 0.0)))

        def fdir(th):
            return math.cos(th) * U + math.sin(th) * Z

        flap_poly = [(0, -Wf / 2), (Lf, -Wf / 2), (Lf, Wf / 2), (0, Wf / 2)]
        ch = min(0.3 * tb, 0.2 * Wf)
        tab_poly = [(-tb, -Wf / 2 + ch), (0, -Wf / 2), (0, Wf / 2), (-tb, Wf / 2 - ch)]
        Tt = frame(H3 + TAB_LIFT * Z, U, Hd)
        tab = self.add(Panel(f"{pf}.Tab", pf, "tab", [tab_poly], lambda t: pa(t) @ Tt, page,
                             None, f"{lab}: hinge tab"))

        def asm_flap(t):
            return pa(t) @ frame(H3 + TAB_LIFT * Z, fdir(theta()), Hd)

        hf = hinge_frame_2d((0, 0), (0, 1))
        flap = self.add(Panel(f"{pf}.Flap", pf, "panel", [flap_poly], asm_flap, tab.name,
                              Hinge(hf, hf, "PULL", dict(var="p", uid=uid,
                                                         fn=lambda q: A * q,
                                                         expr=f"radians({amax:.6g}*p)")),
                              f"{lab}: flap"))

        # the strip: glue end under the flap | link to the slit | under the page
        eps = 2 * TAB_LIFT
        glue_poly = [(-gl, -ws / 2), (0, -ws / 2), (0, ws / 2), (-gl, ws / 2)]

        zl = TAB_LIFT

        def Gs(th):
            """Glue point under the flap (just below its surface), in page coords."""
            f = fdir(th)
            nf = f.cross(Hd)
            return H3 + zl * Z + g * f - eps * nf

        def vparts(th):
            # S - G in (U, Z) components
            c_, s_ = math.cos(th), math.sin(th)
            return (-sl - g * c_ - eps * s_, -zl - g * s_ + eps * c_)

        Lk = math.hypot(*vparts(0.0))
        link_poly = [(0, -ws / 2), (Lk, -ws / 2), (Lk, ws / 2), (0, ws / 2)]
        under_poly = [(Lk, -ws / 2), (Lk + Lu, -ws / 2), (Lk + Lu, ws / 2), (Lk, ws / 2)]

        def asm_glue(t):
            th = theta()
            return pa(t) @ frame(Gs(th), -fdir(th), Hd)

        def asm_link(t):
            th = theta()
            return pa(t) @ frame(Gs(th), (S3 - Gs(th)).normalized(), Hd)

        def d_of(q):
            return Lk - math.hypot(*vparts(A * q))

        Mu0 = frame(S3 - eps * Z, pdir, Hd) @ Matrix.Translation((-Lk, 0, 0))

        def asm_under(t):
            q = max(0.0, min(1.0, self.pull.get(uid, 0.0)))
            return pa(t) @ Matrix.Translation(d_of(q) * pdir) @ Mu0

        glue = self.add(Panel(f"{ps}.Glue", ps, "tab", [glue_poly], asm_glue, flap.name, None,
                              f"{lab}: strip glue end"))
        T = f"radians({amax:.6g}*p)"
        fn_link = (lambda q: math.atan2(vparts(A * q)[1], vparts(A * q)[0]) - A * q)
        ex_link = (f"atan2({-zl:.6g}-{g:.6g}*sin({T})+{eps:.6g}*cos({T}),"
                   f"{-sl:.6g}-{g:.6g}*cos({T})-{eps:.6g}*sin({T}))-{T}")
        hl = hinge_frame_2d((0, 0), (0, 1))
        link = self.add(Panel(f"{ps}.Link", ps, "panel", [link_poly], asm_link, glue.name,
                              Hinge(hl, hl, "PULL", dict(var="p", uid=uid, fn=fn_link, expr=ex_link)),
                              f"{lab}: strip"))
        Fc = frame(Vector((Lk, 0, 0)), (0, -1, 0), (1, 0, 0))
        Hp = Mu0 @ Fc
        # |S - G|^2 = K0 + Kc cos(th) + Ks sin(th)
        K0 = sl * sl + g * g + eps * eps + zl * zl
        Kc = 2 * sl * g - 2 * zl * eps
        Ks = 2 * sl * eps + 2 * zl * g
        ex_d = f"{Lk:.9g}-sqrt({K0:.9g}{Kc:+.9g}*cos({T}){Ks:+.9g}*sin({T}))"
        under = self.add(Panel(f"{ps}.Under", ps, "panel", [under_poly], asm_under, page,
                               Hinge(Hp, Fc, "SLIDE", dict(var="p", uid=uid, fn=d_of, expr=ex_d)),
                               f"{lab}: pull tab"))
        under.outside = True
        self.soft.add(frozenset((link.name, under.name)))
        # slit in the page where the strip comes through
        slot = [S3 + a * U + b * Hd for a, b in ((-0.6, -ws / 2 - 1), (0.6, -ws / 2 - 1),
                                                 (0.6, ws / 2 + 1), (-0.6, ws / 2 + 1))]
        self.carve("Card", [tuple(v[:2]) for v in slot], {page}, lab)
        dmax = d_of(1.0)
        if dmax > out - 3:
            self.warn(f"{lab}: pulling {dmax:.0f} mm needs a longer Pull Tab "
                      f"(it would vanish into the card)")
        self.flaps[uid] = dict(label=lab, travel=dmax)
