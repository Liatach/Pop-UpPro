"""V-fold shapes solved as linkages: the M-fold, zig-zags and multiple
quadrilaterals (Birmingham 28-29, 45-48, 57)."""
import bisect
import math

import numpy as np
from mathutils import Matrix, Vector

from .base import Hinge, Host, Panel, TAB_LIFT
from .geom import hinge_frame_2d, rot_y


_MFOLD_CACHE = {}  # M-fold sides on a card's spine, by shape


class ZigZags:
    """M-fold, zig-zag and quadrilateral builders. Mixed into Model (model.py)."""

    @staticmethod
    def _mgeom(m):
        """An M-fold half's bend, on the piece: (bend point, crease D's
        direction, crease H's, the outer glued edge's), for a half whose
        glued edge runs along up."""
        D = math.radians(float(m.get("m_d", 115.0)))
        E = math.radians(float(m.get("m_e", 45.0)))
        F = math.radians(float(m.get("m_f", 45.0))) if m.get("m_free") else E

        def rot2(v, a):
            c, s_ = math.cos(a), math.sin(a)
            return Vector((c * v.x - s_ * v.y, s_ * v.x + c * v.y))

        def geom(up, g):
            up = Vector(up)
            sx = 1.0 if up.x >= 0 else -1.0
            P = up * g
            k2 = rot2(-up, -sx * D)  # crease D, turning up from the edge back in
            h = rot2(k2, -sx * E)  # crease H, E further out
            e2 = rot2(h, -sx * F)  # the outer glued edge, F further
            return P, k2, h, e2
        return geom

    def _mfold_outer(self, m, host, base, piece, lab, yP, ufs, ups, gs, Lc, tab):
        """Birmingham 28-29, the M-fold: each half's glue line bends (angle
        C on the page) and the piece goes on round its own bend: a crease D
        off the half, a little panel (angle E), crease H, and an outer panel
        (angle F) glued along the line's second part. At each bend four
        creases meet, the half and the outer panel both glued down: a
        linkage with one way to move, solved opening by opening (it closes
        flat when C = D and E = F, the book's rules)."""
        import numpy as np
        Cb = math.radians(float(m.get("m_c", 115.0))) if m.get("m_free") else \
            math.radians(float(m.get("m_d", 115.0)))
        Lh = float(m.get("m_outer_h", 40.0))
        g2 = float(m.get("m_outer_len", 30.0))
        mg = self._mgeom(m)

        def rot2(v, a):
            c, s_ = math.cos(a), math.sin(a)
            return Vector((c * v.x - s_ * v.y, s_ * v.x + c * v.y))

        def npm(M):
            return np.array([[M[i][j] for j in range(4)] for i in range(4)], dtype=float)

        def npry(a):
            c, s_ = math.cos(a), math.sin(a)
            return np.array([[c, 0, s_, 0], [0, 1, 0, 0], [-s_, 0, c, 0], [0, 0, 0, 1.0]])

        Ts = sorted(self.TABLE_T, reverse=True)
        for side in ("L", "R"):
            i_ = 0 if side == "L" else 1
            uf, up = Vector(ufs[i_]), Vector(ups[i_])
            g = gs[side]
            sx = 1.0 if uf.x >= 0 else -1.0
            P, k2, h, e2 = mg(up, g)
            Pb = Vector((0.0, yP)) + uf * g
            w = rot2(-uf, sx * Cb)  # the glue line's second part, on the page
            V = host.R if side == "R" else host.L
            page, Tp = (host.p2, host.T2) if side == "R" else (host.p1, host.T1)
            Hp = hinge_frame_2d(Pb[:], w[:])
            Fc = hinge_frame_2d(P[:], e2[:])
            Fk = hinge_frame_2d(P[:], k2[:])
            half = self.panels.get(f"{base}.Half{side}")
            if half is None:
                return
            nHp, nFci = npm(Hp), npm(Fc.inverted())
            nFk, nFki = npm(Fk), npm(Fk.inverted())
            X = np.array([*(P + h * 10.0), 0.0, 1.0])
            frames = {}

            def at(t):
                got = frames.get(t)
                if got is None:
                    if len(frames) > 50000:
                        frames.clear()
                    got = frames[t] = (npm(V(t)) @ nHp, npm(half.asm(t)) @ nFk)
                return got

            def resid(t, x):
                VH, IK = at(t)
                Mo = VH @ npry(x[0]) @ nFci
                Me = IK @ npry(x[1]) @ nFki
                return (Me @ X - Mo @ X)[:3]

            def solve(t, x0, it=30):
                x = np.array(x0, dtype=float)
                for _ in range(it):
                    r = resid(t, x)
                    if np.abs(r).max() < 1e-7:
                        return x, True
                    J = np.zeros((3, 2))
                    for j in range(2):
                        dx = np.zeros(2)
                        dx[j] = 1e-7
                        J[:, j] = (resid(t, x + dx) - r) / 1e-7
                    step = np.linalg.lstsq(J, -r, rcond=None)[0]
                    n_ = np.abs(step).max()
                    if n_ > 0.5:
                        step *= 0.5 / n_
                    x = x + step
                    if n_ < 1e-8:
                        break  # (as close as single precision allows)
                # (the half's pose comes in single precision: good to ~1e-5 mm)
                return x, bool(np.abs(resid(t, x)).max() < 2e-4)

            def above(t, x):
                VH, _ = at(t)
                Mo = VH @ npry(x[0]) @ nFci
                Vt = npm(V(t))
                n = Vt[:3, 2]
                o = Vt[:3, 3]
                return min(float((Mo @ np.array([*(P + e2 * g2 + h * Lh), 0.0, 1.0]))[:3] @ n
                                 - o @ n),
                           float((Mo @ np.array([*(P + h * Lh), 0.0, 1.0]))[:3] @ n - o @ n))

            key = None
            if (host.p1, host.p2) == ("Page.L", "Page.R"):
                key = (side, tuple(round(float(c), 7) for c in (*uf, *up, *w, *P, *k2, *h, *e2)),
                       g, Lh, g2, hash(tuple(self.TABLE_T)))
            got = _MFOLD_CACHE.get(key) if key else None
            if got is not None:
                tab_, solved, ws = got
                for w_ in ws:
                    self.warn(w_)
            else:
                nw = len(self.warnings)
                # the outer panel's crease H must reach from crease D's cone to
                # the glue line's: past some opening it can't (the M-fold
                # holds the card from opening further)
                Ek = math.radians(float(m.get("m_e", 45.0)))
                Fa = math.radians(float(m.get("m_f", 45.0))) if m.get("m_free") else Ek

                def gap(t):
                    k3 = npm(half.asm(t))[:3, :3] @ np.array([k2.x, k2.y, 0.0])
                    w3 = npm(V(t))[:3, :3] @ np.array([w.x, w.y, 0.0])
                    a_ = math.acos(max(-1.0, min(1.0, float(k3 @ w3 / np.linalg.norm(k3)
                                                             / np.linalg.norm(w3)))))
                    return min(Ek + Fa - a_, a_ - abs(Ek - Fa))
                Tok = [t for t in Ts if gap(t) > 0.04]  # (clear of where it locks)
                if not Tok:
                    self.warn(f"{lab}: M-fold's angles can't meet at any opening; skipped")
                    return
                t_open = Tok[0]
                if t_open < Ts[0] - 0.5 and side == "R":
                    self.warn(f"{lab}: M-fold holds the card from opening past about "
                              f"{t_open:.0f} degrees (more angle E would let it open further)")
                cands = []
                for i in range(5):
                    for j in range(5):
                        x0 = (-math.pi + (i + 0.5) * 0.4 * math.pi,
                              -math.pi + (j + 0.5) * 0.4 * math.pi)
                        x, ok = solve(t_open, x0)
                        if ok and above(t_open, x) > -0.5 and \
                                all(np.abs(np.remainder(x - c + math.pi, 2 * math.pi) - math.pi)
                                    .max() > 1e-4 for c in cands):
                            cands.append(x)
                Ts_ = [t for t in Ts if t <= t_open]
                best = None
                for x in cands:
                    tb, bad = {}, None
                    for t in Ts_:
                        x2, ok = solve(t, x)
                        if not ok or np.abs(x2 - x).max() > 0.3:
                            bad = t
                            break
                        x = x2
                        tb[t] = x
                    flat = 9.0
                    if bad is None:
                        x_s = tb[Ts[-1]]
                        flat = float(max(abs(math.remainder(float(c), math.pi)) for c in x_s))
                    low = min(above(t, tb[t]) for t in list(tb)[::6]) if tb else -99.0
                    score = (bad is not None, low < -1.0, flat > math.radians(4.0), -low)
                    if best is None or score < best[0]:
                        best = (score, tb, bad)
                if best is None:
                    self.warn(f"{lab}: M-fold's outer panels can't stand with these angles; "
                              f"skipped")
                    return
                (fail, low_, notflat, _), tab_, bad = best
                for t in Ts:
                    if t > t_open:
                        tab_[t] = tab_[t_open]  # (held: it goes no further)
                if fail:
                    self.warn(f"{lab}: M-fold jams closing past {bad:.0f} degrees; check its "
                              f"angles")
                    last = tab_[min(tab_)] if tab_ else cands[0]
                    for t in Ts:
                        tab_.setdefault(t, last)
                elif notflat and side == "R":
                    self.warn(f"{lab}: M-fold doesn't fold flat: keep C = D and E = F (the "
                              f"book's rules), or adjust them together")
                solved = {}
                if key:
                    if len(_MFOLD_CACHE) > 40:
                        _MFOLD_CACHE.clear()
                    _MFOLD_CACHE[key] = (tab_, solved, list(self.warnings[nw:]))
            keys = sorted(tab_)

            def x_at(t, tab_=tab_, solved=solved, keys=keys, solve=solve):
                t = min(max(t, keys[0]), keys[-1])
                got = tab_.get(t)
                if got is None:
                    got = solved.get(t)
                if got is None:
                    i = max(0, min(len(keys) - 2, bisect.bisect_right(keys, t) - 1))
                    a_, b_ = keys[i], keys[i + 1]
                    f = (t - a_) / (b_ - a_)
                    # (between the table's openings: the angles interpolated;
                    # the half it hangs off is exact anyway)
                    got = tab_[a_] + f * (tab_[b_] - tab_[a_])
                return got

            def asm_o(t, V=V, Hp=Hp, Fci=Fc.inverted(), x_at=x_at):
                return V(t) @ Hp @ rot_y(float(x_at(t)[0])) @ Fci

            def asm_e(t, ha=half.asm, Fk=Fk, Fki=Fk.inverted(), x_at=x_at):
                return ha(t) @ Fk @ rot_y(float(x_at(t)[1])) @ Fki
            Et = P + e2 * g2
            # (hinge angles counted from where it lies shut, so they never
            # wrap round past half a turn)
            x0_ = tab_[keys[0]]
            self.add(Panel(f"{base}.E{side}", piece, "panel",
                           [[P[:], (P + k2 * Lh)[:], (P + h * Lh)[:]]], asm_e, half.name,
                           Hinge(Fk @ rot_y(float(x0_[1])), Fk, "TABLE"),
                           f"{lab}: shoulder {side} (E)"))
            self.add(Panel(f"{base}.Outer{side}", piece, "panel",
                           [[P[:], Et[:], (Et + h * Lh)[:], (P + h * Lh)[:]]], asm_o, page,
                           Hinge(Tp @ Hp @ rot_y(float(x0_[0])), Fc, "TABLE"),
                           f"{lab}: outer panel {side} (F)"))
            # the outer panel's tab, folded under it and glued down
            n_out = Vector((-e2.y, e2.x))
            if n_out.dot(h) > 0:
                n_out = -n_out
            ins = min(0.5 * tab, 0.3 * g2)
            tp = [P[:], Et[:], (Et + n_out * tab - e2 * ins)[:], (P + n_out * tab + e2 * ins)[:]]
            lift = host.lift[1 if side == "R" else 0] * TAB_LIFT
            Ttab = Tp @ Matrix.Translation((0.0, 0.0, lift)) @ Hp @ rot_y(math.pi) @ \
                Fc.inverted()
            pa_ = self.panels[page].asm
            self.add(Panel(f"{base}.OuterTab{side}", piece, "tab", [tp],
                           (lambda t, pa=pa_, T=Ttab: pa(t) @ T), page, None,
                           f"{lab}: tab {side} (outer)"))

    # ------------------------------------------- walls on angled strips
    @staticmethod
    def _lengths(text, default):
        out = []
        for tok in str(text or "").replace(";", ",").split(","):
            tok = tok.strip()
            if tok:
                try:
                    v = float(tok)
                except ValueError:
                    continue
                if v > 0.5:
                    out.append(v)
        return out or list(default)

    def _strips(self, m, lab):
        from .linkage import Plan
        host = self.placed.get(m["uid"])
        C = math.radians(float(m.get("phi_l", 60.0)))
        if not (5.0 <= math.degrees(C) <= 85.0 or 95.0 <= math.degrees(C) <= 175.0):
            self.warn(f"{lab}: the strips can't run square across the spine; using 60")
            C = math.radians(60.0)
        return Plan(self, host, C, float(m.get("x", 20.0)), float(m.get("width", 25.0)),
                    float(m.get("y", 60.0)))

    def _zigzag(self, m, host):
        """Birmingham 45-48, zig-zag folds: a strip of walls, all its creases
        square to its bottom edge, glued only by its two end walls along
        sticking strips set at an angle to the spine. The walls in between
        zig-zag out from the strips to a centre crease on the spine's line."""
        from .linkage import build
        lab = m["label"]
        P = self._strips(m, lab)
        faces = self._lengths(m.get("faces", ""), [30.0])[:6]
        jut = 1.0 if m.get("jut", "FRONT") == "FRONT" else -1.0
        A = np.array(P.vA) - np.array((0.0, P.y0))
        tot = sum(faces)
        if tot <= abs(A[0]) + 0.5:
            self.warn(f"{lab}: its faces are too narrow to reach the centre from the "
                      f"strips; skipped")
            return
        # open flat: from the strip's inner end out to the centre crease,
        # zig-zagging on the way
        ey = A[1] - jut * math.sqrt(max(tot * tot - A[0] * A[0], 0.0)) * 0.85
        E = np.array((0.0, ey))
        names = [f"N{k}" for k in range(1, len(faces))]
        prev = "A.R"
        for k, n in enumerate(names):
            f = sum(faces[:k + 1]) / tot
            g = A + f * (E - A)
            dirv = (E - A) / max(np.linalg.norm(E - A), 1e-9)
            nrm = np.array((-dirv[1], dirv[0]))
            g = g + nrm * (0.35 * faces[k] * (1 if k % 2 == 0 else -1) * jut)
            P.add_free(n, (g[0], g[1] + P.y0))
            P.bar(prev, n + ".R", faces[k])
            prev = n + ".R"
        P.add_mid("E", ey + P.y0)
        P.bar(prev, "E", faces[-1])
        for w_ in P.run():
            self.warn(f"{lab}: {w_}")
        h = float(m.get("height", 50.0))
        right = ["A.R"] + [n + ".R" for n in names] + ["E"]
        left = ["B.L", "A.L"] + [n + ".L" for n in names]
        chain = left + ["E"] + [x for x in reversed(right[:-1])] + ["B.R"]
        pieces = [dict(key="Z", label="zig-zag", nodes=chain, heights=[h] * (len(chain) - 1),
                       glued=(True, True))]
        self.line_frames[m["uid"]] = (f"Link{m['uid']}.Z", lambda q: q, None)
        walls = build(self, m, host, P, pieces, lab, float(m.get("tab", 10.0)))
        # its centre crease takes other mechanisms, as a V-fold's does
        kL, kR = len(left) - 1, len(left)
        nL, nR = f"Link{m['uid']}.Z{kL}", f"Link{m['uid']}.Z{kR}"
        if nL in self.panels and nR in self.panels:
            wl = walls[f"Z{kL}"]
            xE = wl["x0"] + wl["L"]
            hh = Host(self, nL, xE, 0.0, nR, xE, 0.0, f"{lab}: crease").finish()
            hh.trig = False
            hh.size = (faces[-1], h)
            hh.key = (m["uid"], "V")
            self.hosts[(m["uid"], "V")] = hh

    def _quads(self, m, host):
        """Birmingham 57, multiple quadrilaterals: a back zig-zag glued by its
        end walls to angled strips (strip end A, back crease D, centre E), a
        side piece each side from the strip's far end B to a front corner C
        and back to D, in line with the back's centre face, and a front strip
        from C across the spine (centre F). Quadrilateral ABCD's two ways
        round, from back crease to front corner, are made equal (the book's
        AB + BC = AD + DC) so it folds flat: B to C is worked out to suit."""
        from .linkage import build
        lab = m["label"]
        P = self._strips(m, lab)
        ad, de = (self._lengths(m.get("faces", ""), [16.0, 16.0]) + [16.0])[:2]
        cd = float(m.get("depth", 25.0))
        cf = float(m.get("front", 30.0))
        ab = P.w0
        bc = ad + cd - ab
        if bc < 3.0:
            self.warn(f"{lab}: the side piece's face to the strip comes out too short "
                      f"({bc:.0f} mm); make Side or the back's first face longer")
            return
        A = np.array(P.vA)
        Bv = np.array(P.vB)
        # the back zig-zag sits on the side the strips spread towards, the
        # front strip on the other
        sy = -1.0 if math.cos(P.C) > 0 else 1.0

        def layout(th):
            # open flat (the plan is then the page): D round A, E behind it on
            # the spine's line, C on past D in line with E
            D = A + ad * np.array((-math.cos(th), sy * math.sin(th)))
            if de < abs(D[0]):
                return None
            E = np.array((0.0, D[1] + sy * math.sqrt(de * de - D[0] * D[0])))
            u = (D - E) / max(np.linalg.norm(D - E), 1e-9)
            return D, E, D + u * cd
        best = None
        for i in range(1, 400):
            th = -0.5 * math.pi + math.pi * i / 400
            got = layout(th)
            if got is None:
                continue
            gap = abs(float(np.linalg.norm(got[2] - Bv)) - bc)
            if got[2][0] > 0 and (best is None or gap < best[0]):
                best = (gap, th)
        if best is None or best[0] > 5.0:
            self.warn(f"{lab}: these lengths can't make the quadrilateral; skipped")
            return
        lo, hi = best[1] - math.pi / 400, best[1] + math.pi / 400
        f = (lambda th: float(np.linalg.norm(layout(th)[2] - Bv)) - bc)
        for _ in range(60):
            mid = 0.5 * (lo + hi)
            if layout(lo) is None or layout(mid) is None:
                break
            if (f(lo) > 0) == (f(mid) > 0):
                lo = mid
            else:
                hi = mid
        D, E, Cn = layout(0.5 * (lo + hi))
        if cf < Cn[0]:
            self.warn(f"{lab}: the front can't reach the centre; make Front longer")
            return
        F = (0.0, Cn[1] - sy * math.sqrt(max(cf * cf - Cn[0] * Cn[0], 0.0)))
        P.add_free("D", tuple(D))
        P.add_free("C", tuple(Cn))
        P.add_mid("E", E[1])
        P.add_mid("F", F[1])
        P.bar("A.R", "D.R", ad)
        P.bar("D.R", "E", de)
        P.bar("B.R", "C.R", bc)
        P.bar("C.R", "D.R", cd)
        P.bar("C.R", "F", cf)
        P.line("C.R", "D.R", "E")
        for w_ in P.run():
            self.warn(f"{lab}: {w_}")
        hb = float(m.get("height", 50.0))
        hs = float(m.get("back", 30.0))
        hf = float(m.get("img_h", 25.0))
        pieces = [
            dict(key="K", label="back", nodes=["B.L", "A.L", "D.L", "E", "D.R", "A.R", "B.R"],
                 heights=[hb] * 6, glued=(True, True)),
            dict(key="SL", label="left side", nodes=["B.L", "C.L", "D.L"], heights=[hs] * 2,
                 glued=(False, False), first=("K0", "B.L"), last=("K2", "D.L")),
            dict(key="SR", label="right side", nodes=["B.R", "C.R", "D.R"], heights=[hs] * 2,
                 glued=(False, False), first=("K5", "B.R"), last=("K3", "D.R")),
            dict(key="F", label="front", nodes=["C.L", "F", "C.R"], heights=[hf] * 2,
                 glued=(False, False), first=("SL0", "C.L"), last=("SR0", "C.R")),
        ]
        self.line_frames[m["uid"]] = (f"Link{m['uid']}.K", lambda q: q, None)
        walls = build(self, m, host, P, pieces, lab, float(m.get("tab", 10.0)))
        # the back's centre crease takes other mechanisms
        nL, nR = f"Link{m['uid']}.K2", f"Link{m['uid']}.K3"
        if nL in self.panels and nR in self.panels:
            xE = walls["K2"]["x0"] + walls["K2"]["L"]
            hh = Host(self, nL, xE, 0.0, nR, xE, 0.0, f"{lab}: back crease").finish()
            hh.trig = False
            hh.size = (de, hb)
            hh.key = (m["uid"], "V")
            self.hosts[(m["uid"], "V")] = hh
