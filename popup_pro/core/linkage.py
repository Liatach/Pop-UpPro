"""Walls standing on two sticking strips glued at an angle to the spine,
every crease at right angles to the walls' bottom edges (Birmingham 45-48,
the zig-zags, and 57, multiple quadrilaterals).

Each end wall is glued along its bottom edge to a strip, so every crease
in the piece runs square to both strips at once: along d = gR x gL. Seen
along d the walls are a flat linkage: the strips' ends are fixed points,
the creases are joints, the walls are bars. That plan is solved opening by
opening (in double precision, staying as close as it can to the opening
before when the linkage has slack) and the walls stood up along d from a
common foot plane. Everything is mirror symmetric about the spine.

At full opening d is straight up and the plan is the page itself, so the
positions given for the creases there are just where they stand on the
card when it is open flat."""

import bisect
import math

import numpy as np
from mathutils import Matrix, Vector

from .geom import frame, hinge_frame_2d, rot_y

MIR = ".L"
_CACHE = {}  # solved linkages on a card's spine, by shape (moving one up or
# down the spine changes nothing in its plan)


def _np(M):
    return np.array([[M[i][j] for j in range(4)] for i in range(4)], dtype=float)


class Plan:
    """The linkage: nodes and bars, solved at each opening."""

    def __init__(self, model, host, C, B, w0, y0):
        self.mo, self.host = model, host
        self.C, self.B, self.w0, self.y0 = C, B, w0, y0
        s, c = math.sin(C), math.cos(C)
        self.sgn = 1.0 if c > 0 else -1.0
        # the strips (right side, virtual page coordinates): A the end
        # nearer the spine, B the far end
        self.vA = (B * s, y0 + B * c)
        self.vB = ((B + w0) * s, y0 + (B + w0) * c)
        self.free = []  # right-side nodes (x, y unknown)
        self.mid = []  # nodes on the spine's mirror plane (y unknown)
        self.bars = []  # (node, node, length)
        self.lines = []  # (node, node, node) kept in a straight line
        self.guess = {}
        self.tables = None
        self.solved = {}
        self._fr = {}

    # ---- naming: "X.R" right, "X.L" its mirror, "X" on the mirror plane
    def add_free(self, name, guess):
        self.free.append(name)
        self.guess[name + ".R"] = (guess[0], guess[1] - self.y0)

    def add_mid(self, name, gy):
        self.mid.append(name)
        self.guess[name] = (0.0, gy - self.y0)

    def bar(self, a, b, L):
        self.bars.append((a, b, float(L)))

    def line(self, a, b, c):
        self.lines.append((a, b, c))

    # ---- the fixed parts at an opening
    def frame_at(self, t):
        got = self._fr.get(t)
        if got is not None:
            return got
        h = self.host
        L, R = _np(h.L(t)), _np(h.R(t))
        s, c = math.sin(self.C), math.cos(self.C)
        gR = R[:3, :3] @ np.array([s, c, 0.0])
        gL = L[:3, :3] @ np.array([-s, c, 0.0])
        d = np.cross(gR, gL) * self.sgn
        d /= np.linalg.norm(d)
        S = (L @ np.array([0.0, self.y0, 0.0, 1.0]))[:3]  # where the strips' lines meet
        dR = R[:3, :3] @ np.array([1.0, 0.0, 0.0])
        dL = L[:3, :3] @ np.array([-1.0, 0.0, 0.0])
        m = dR - dL
        if np.linalg.norm(m) < 1e-12:
            m = R[:3, :3] @ np.array([0.0, 0.0, 1.0])
        m = m - d * (m @ d)
        m /= np.linalg.norm(m)
        e2 = np.cross(d, m)
        A3 = (R @ np.array([self.vA[0], self.vA[1], 0.0, 1.0]))[:3]
        B3 = (R @ np.array([self.vB[0], self.vB[1], 0.0, 1.0]))[:3]
        h0 = (A3 - S) @ d

        def plan(X):
            return np.array([(X - S) @ m, (X - S) @ e2])
        got = self._fr[t] = dict(S=S, m=m, e2=e2, d=d, h0=h0, A=plan(A3), B=plan(B3))
        if len(self._fr) > 50000:
            self._fr.clear()
        return got

    def _compile(self):
        """Index the nodes once: positions = fixed + G q."""
        names = ["A.R", "B.R", "A.L", "B.L"]
        names += [n + ".R" for n in self.free] + [n + MIR for n in self.free] + list(self.mid)
        self.names = names
        self.idx = {n: i for i, n in enumerate(names)}
        N, nq = len(names), 2 * len(self.free) + len(self.mid)
        G = np.zeros((2 * N, nq))
        k = 0
        for n in self.free:
            iR, iL = self.idx[n + ".R"], self.idx[n + MIR]
            G[2 * iR, k], G[2 * iR + 1, k + 1] = 1.0, 1.0
            G[2 * iL, k], G[2 * iL + 1, k + 1] = -1.0, 1.0
            k += 2
        for n in self.mid:
            G[2 * self.idx[n] + 1, k] = 1.0
            k += 1
        self.G = G
        self.ia = np.array([self.idx[a] for a, _, _ in self.bars], dtype=int)
        self.ib = np.array([self.idx[b] for _, b, _ in self.bars], dtype=int)
        self.L = np.array([L for _, _, L in self.bars])
        self.li = [tuple(self.idx[x] for x in tri) for tri in self.lines]

    def _pos(self, t, q):
        if not hasattr(self, "G"):
            self._compile()
        F = self.frame_at(t)
        P0 = np.zeros((len(self.names), 2))
        P0[0], P0[1] = F["A"], F["B"]
        P0[2] = (-F["A"][0], F["A"][1])
        P0[3] = (-F["B"][0], F["B"][1])
        return P0 + (self.G @ np.asarray(q, dtype=float)).reshape(-1, 2)

    def nodes(self, t, q):
        """All node positions (plan) from the unknowns q."""
        P = self._pos(t, q)
        return {n: P[i] for i, n in enumerate(self.names)}

    def _rj(self, t, q, jac=True):
        P = self._pos(t, q)
        D = P[self.ia] - P[self.ib]
        ln = np.linalg.norm(D, axis=1)
        r = ln - self.L
        J = None
        if jac:
            U = D / np.maximum(ln, 1e-12)[:, None]
            Jp = np.zeros((len(self.L), 2 * len(self.names)))
            rows = np.arange(len(self.L))
            Jp[rows, 2 * self.ia] += U[:, 0]
            Jp[rows, 2 * self.ia + 1] += U[:, 1]
            Jp[rows, 2 * self.ib] -= U[:, 0]
            Jp[rows, 2 * self.ib + 1] -= U[:, 1]
            J = Jp @ self.G
        if self.li:
            rl, Jl = [], []
            for a, b, c in self.li:
                ids = (a, b, c)

                def f(x):
                    u = x[2:4] - x[0:2]
                    v = x[4:6] - x[2:4]
                    return (u[0] * v[1] - u[1] * v[0]) / max(math.hypot(v[0], v[1]), 1e-9)
                x0 = np.concatenate([P[a], P[b], P[c]])
                f0 = f(x0)
                rl.append(f0)
                if jac:
                    row = np.zeros(2 * len(self.names))
                    for j in range(6):
                        x1 = x0.copy()
                        x1[j] += 1e-7
                        row[2 * ids[j // 2] + j % 2] = (f(x1) - f0) / 1e-7
                    Jl.append(row @ self.G)
            r = np.concatenate([r, rl])
            if jac:
                J = np.vstack([J, np.array(Jl)])
        return r, J

    def resid(self, t, q):
        return self._rj(t, q, False)[0]

    def solve(self, t, q0, qref, mu, it=60):
        q = np.array(q0, dtype=float)
        qref = np.array(qref, dtype=float)
        lam = 1e-6
        n = len(q)
        r, J = self._rj(t, q)
        c0 = r @ r + mu * ((q - qref) @ (q - qref))
        for _ in range(it):
            g = J.T @ r + mu * (q - qref)
            Hm = J.T @ J + mu * np.eye(n)
            while True:
                try:
                    step = np.linalg.solve(Hm + lam * np.eye(n), -g)
                except np.linalg.LinAlgError:
                    lam *= 10.0
                    continue
                q1 = q + step
                r1, _ = self._rj(t, q1, False)
                c1 = r1 @ r1 + mu * ((q1 - qref) @ (q1 - qref))
                if c1 <= c0:
                    q, c0 = q1, c1
                    r, J = self._rj(t, q)
                    lam = max(lam * 0.3, 1e-12)
                    break
                lam *= 10.0
                if lam > 1e8:
                    return q, float(np.abs(r).max())
            if np.abs(step).max() < 1e-11 or float(np.abs(r).max()) < 1e-12:
                break
        return q, float(np.abs(r).max())

    def q_from_guess(self):
        q = []
        for n in self.free:
            q += list(self.guess[n + ".R"])
        for n in self.mid:
            q.append(self.guess[n][1])
        return np.array(q, dtype=float)

    def flat_cost(self, t, q):
        P = self.nodes(t, q)
        return max(abs(v[0]) for v in P.values())

    def _key(self):
        h = self.host
        if (h.p1, h.p2) != ("Page.L", "Page.R"):
            return None
        r = (lambda v: round(float(v), 6))
        return (r(self.C), r(self.B), r(self.w0), tuple(self.free), tuple(self.mid),
                tuple((a, b, r(L)) for a, b, L in self.bars), tuple(self.lines),
                tuple(sorted((k, r(v[0]), r(v[1])) for k, v in self.guess.items())),
                hash(tuple(self.mo.TABLE_T)))

    def run(self):
        key = self._key()
        got = _CACHE.get(key) if key is not None else None
        if got is not None:
            self.tables, self.keys, self.jammed, self.solved, warn = got
            return list(warn)
        warn = self._run()
        if key is not None:
            if len(_CACHE) > 24:
                _CACHE.clear()
            _CACHE[key] = (self.tables, self.keys, self.jammed, self.solved, list(warn))
        return warn

    def _run(self):
        """Tabulate the linkage; returns warnings. Where the lengths leave
        slack, it closes as gently as it can while ending flat."""
        mo = self.mo
        warn = []
        Ts = sorted(mo.TABLE_T, reverse=True)
        g = self.q_from_guess()
        # fully open: as near the drawn positions as the lengths allow
        q, _ = self.solve(Ts[0], g, g, 1e-3, 200)
        q, err = self.solve(Ts[0], q, q, 1e-9, 200)
        if err > 1e-4:
            warn.append(f"its lengths don't fit together ({err:.1f} mm out)")
        q_open = q
        # pass 1: the least motion from one opening to the next
        p1 = {}
        for t in Ts:
            q2, err = self.solve(t, q, q, 1e-7)
            if err > 1e-3:
                break
            q = q2
            p1[t] = q
        t_shut = Ts[-1]
        tab = {}
        if t_shut in p1 and self.flat_cost(t_shut, p1[t_shut]) > 0.5:
            # pass 2: steer the slack towards the nearest flat pose when shut
            qs = p1[t_shut]
            n_x = [k for k, _ in enumerate(qs)]

            def flat_resid(q_):
                P = self.nodes(t_shut, q_)
                return np.array([v[0] for v in P.values()] + list(self.resid(t_shut, q_)))
            def gn(q0):
                qf = q0.copy()
                for _ in range(60):
                    r = flat_resid(qf)
                    J = np.zeros((len(r), len(qf)))
                    for i in n_x:
                        dq = np.zeros(len(qf))
                        dq[i] = 1e-7
                        J[:, i] = (flat_resid(qf + dq) - r) / 1e-7
                    step = np.linalg.lstsq(J, -r, rcond=None)[0]
                    qf = qf + step
                    if np.abs(step).max() < 1e-10:
                        break
                return qf, float(np.abs(flat_resid(qf)).max())
            # the flat poses are a few discrete foldings: try from several
            # starts, keep the nearest that fits
            rng = np.random.default_rng(7)
            starts = [qs]
            k = 0
            flat0 = qs.copy()
            for nm in self.free:
                flat0[k] = 0.0
                k += 2
            starts.append(flat0)
            for _ in range(40):
                starts.append(flat0 + rng.normal(0.0, 15.0, len(qs)))
            cands = []
            for q0 in starts:
                qf_, e_ = gn(q0)
                if e_ < 0.1 and all(float(np.abs(qf_ - c_).max()) > 0.5 for c_ in cands):
                    cands.append(qf_)
            cands.sort(key=lambda c_: float(np.abs(c_ - qs).sum()))
            for qf in cands[:6]:
                q = q_open
                tab = {}
                for t in Ts:
                    f = 1.0 - (t - t_shut) / (Ts[0] - t_shut)
                    ref = p1.get(t, q) + f * (qf - qs)
                    # a nudge at a time, so it never jumps to another way of
                    # folding up
                    dv = ref - q
                    n_ = float(np.abs(dv).max())
                    if n_ > 0.6:
                        dv *= 0.6 / n_
                    q2, _ = self.solve(t, q, q + dv, 1e-3)
                    q2, err = self.solve(t, q2, q2, 1e-9)
                    if err < 1e-3 and float(np.abs(q2 - q).max()) > 4.0:
                        err = 1.0  # (it jumped)
                    if err > 1e-3:
                        tab = {}
                        break
                    q = q2
                    tab[t] = q
                if tab and self.flat_cost(t_shut, tab[t_shut]) < 1.0:
                    break
                tab = {}
        if not tab:
            tab = dict(p1)
            if len(p1) < len(Ts):
                bad = max(t for t in Ts if t not in p1)
                warn.append(f"jams closing past {bad:.0f} degrees")
                last = p1[min(p1)] if p1 else q_open
                for t_ in Ts:
                    tab.setdefault(t_, last)
        self.tables = tab
        self.keys = sorted(tab)
        self.jammed = any(w_.startswith("jams") for w_ in warn)
        # shut: everything should lie flat (on the line of the strips)
        off = self.flat_cost(self.keys[0], tab[self.keys[0]])
        if off > 1.0 and not warn:
            warn.append(f"doesn't fold flat (sticks out about {off:.0f} mm when shut): "
                        f"check its lengths balance")
        return warn

    def q_at(self, t):
        Tk = self.keys
        t = min(max(t, Tk[0]), Tk[-1])
        got = self.tables.get(t)
        if got is not None:
            return got
        got = self.solved.get(t)
        if got is not None:
            return got
        i = max(0, min(len(Tk) - 2, bisect.bisect_right(Tk, t) - 1))
        a_, b_ = Tk[i], Tk[i + 1]
        f = (t - a_) / (b_ - a_)
        qi = self.tables[a_] + f * (self.tables[b_] - self.tables[a_])
        q, _ = self.solve(t, qi, qi, 1e-7, 30)
        if len(self.solved) > 50000:
            self.solved.clear()
        self.solved[t] = q
        return q

    def point(self, t, node, z=0.0):
        got = self._pts.get(t) if hasattr(self, "_pts") else None
        if got is None:
            if not hasattr(self, "_pts") or len(self._pts) > 50000:
                self._pts = {}
            F = self.frame_at(t)
            P = self._pos(t, self.q_at(t))
            got = self._pts[t] = (F, {n: P[i] for i, n in enumerate(self.names)})
        F, P = got
        p = P[node]
        return F["S"] + p[0] * F["m"] + p[1] * F["e2"] + (F["h0"] + z) * F["d"]


def build(model, m, host, plan, pieces, lab, tab):
    """Panels for the walls. pieces: [dict(key, label, nodes, heights,
    glued=(first wall glued?, last wall glued?), first=(wall, node) or None,
    last=(wall, node) or None)], wall names "<piece key><k>"; a piece's first
    wall hangs on `first` (a crease across pieces, with a tab glued on that
    wall) and its last end is tabbed onto `last`."""
    from .model import Panel, Hinge, Piece, TAB_LIFT
    uid = m["uid"]
    base = f"Link{uid}"
    walls = {}  # name -> dict(piece, a, b, x0, L, h)
    for pc in pieces:
        x = 0.0
        ns = pc["nodes"]
        for k in range(len(ns) - 1):
            a, b = ns[k], ns[k + 1]
            p0 = plan.nodes(model.TABLE_T[-1], plan.tables[max(plan.tables)])
            L = float(np.linalg.norm(p0[a] - p0[b]))
            walls[f"{pc['key']}{k}"] = dict(piece=f"{base}.{pc['key']}", a=a, b=b, x0=x,
                                            L=L, h=float(pc["heights"][k]), pc=pc, k=k)
            x += L

    def wall_asm(w):
        def asm(t, w=w):
            Xa = plan.point(t, w["a"])
            Xb = plan.point(t, w["b"])
            d = plan.frame_at(t)["d"]
            M = frame(Vector(Xa), Vector(Xb - Xa), Vector(d))
            return M @ Matrix.Translation((-w["x0"], 0.0, 0.0))
        return asm

    # where the walls' common foot would dip into a page (as the card opens
    # and closes the strips tip it), their bottom edges are cut away to
    # clear it
    how = m.get("cut_bottoms", "LIGHT")
    slack = 0.6 if how == "CLEAR" else 3.0  # (mm a bottom may rub on a page)
    clear = {}
    for pc in pieces:
        for n in pc["nodes"]:
            if n in clear:
                continue
            if n[0] in "AB" and n[1:] in (".L", ".R"):
                clear[n] = 0.0  # (on a strip's glue line)
                continue
            # (only where it would really dig in: card gives a little, and
            # nearly shut everything is lying down anyway)
            if how == "NONE":
                clear[n] = 0.0
                continue
            worst = 0.0
            for t in model.TABLE_T[::2]:
                if t < 12.0:
                    continue
                Lo, _, _, _, nL, nR = host.dirs(t)
                X = Vector(plan.point(t, n))
                d = Vector(plan.frame_at(t)["d"])
                for nn in (nL, nR):
                    dip = -(X - Lo).dot(nn) - slack
                    if dip > 0.0:
                        up = d.dot(nn)  # (how much a step up the crease lifts it)
                        if up > 0.2:
                            worst = max(worst, dip / up)
            clear[n] = worst + 0.5 if worst > 0.05 else 0.0
    plan.clear = clear

    slot = 1 + uid
    for i, pc in enumerate(pieces):
        model.add_piece(Piece(f"{base}.{pc['key']}", f"{lab}: {pc['label']}", slot + 100 * i,
                              (0.0, 0.3 * 297.0)))
    s, c = math.sin(plan.C), math.cos(plan.C)
    # virtual strip points, each side (for the glued walls' hinges and tabs)
    vpts = {"A.R": plan.vA, "B.R": plan.vB, "A.L": (-plan.vA[0], plan.vA[1]),
            "B.L": (-plan.vB[0], plan.vB[1])}
    for pc in pieces:
        ns = pc["nodes"]
        for k in range(len(ns) - 1):
            name = f"{pc['key']}{k}"
            w = walls[name]
            ca, cb = clear.get(w["a"], 0.0), clear.get(w["b"], 0.0)
            if max(ca, cb) > w["h"] - 3.0:
                model.warn(f"{lab}: {pc['label']} {k + 1} would dip right into the page; "
                           f"make it taller or the strips steeper")
                ca, cb = min(ca, w["h"] - 3.0), min(cb, w["h"] - 3.0)
            poly = [(w["x0"], ca), (w["x0"] + w["L"], cb), (w["x0"] + w["L"], w["h"]),
                    (w["x0"], w["h"])]
            glued = (k == 0 and pc["glued"][0]) or (k == len(ns) - 2 and pc["glued"][1])
            pname = f"{base}.{name}"
            if k == 0 and pc["glued"][0] or k == 0 and pc.get("first") is None:
                # root: glued along its bottom edge to a page
                side = w["a"][-1] if w["a"][-1] in "LR" else "L"
                page, Tp = (host.p2, host.T2) if side == "R" else (host.p1, host.T1)
                va, vb = vpts[w["a"]], vpts[w["b"]]
                Hp = Tp @ hinge_frame_2d(va, (vb[0] - va[0], vb[1] - va[1]))
                Fc = hinge_frame_2d((w["x0"], 0.0), (1.0, 0.0))
                parent, hinge = page, Hinge(Hp, Fc, "TABLE")
            elif k == 0:
                # hangs on a wall of another piece, along their shared crease
                wn, node = pc["first"]
                W = walls[wn]
                xw = W["x0"] if node == W["a"] else W["x0"] + W["L"]
                Hp = hinge_frame_2d((xw, 0.0), (0.0, 1.0))
                Fc = hinge_frame_2d((w["x0"], 0.0), (0.0, 1.0))
                parent, hinge = f"{base}.{wn}", Hinge(Hp, Fc, "TABLE")
            else:
                Hc = hinge_frame_2d((w["x0"], 0.0), (0.0, 1.0))
                parent, hinge = f"{base}.{pc['key']}{k - 1}", Hinge(Hc, Hc, "TABLE")
            if getattr(plan, "jammed", False):
                hinge.host_bound = True  # (it can't follow all the way: warn, don't fail)
            pn = model.add(Panel(pname, w["piece"], "panel", [poly], wall_asm(w), parent,
                                 hinge, f"{lab}: {pc['label']} {k + 1}"))
            if pn is not None:
                pn.rub = 1e9 if how == "NONE" else slack + 0.5
            if glued:
                side = w["a"][-1] if w["a"][-1] in "LR" else w["b"][-1]
                page, Tp = (host.p2, host.T2) if side == "R" else (host.p1, host.T1)
                va, vb = vpts[w["a"]], vpts[w["b"]]
                Hp = Tp @ Matrix.Translation((0.0, 0.0, TAB_LIFT * host.lift[
                    1 if side == "R" else 0])) @ hinge_frame_2d(va, (vb[0] - va[0], vb[1] - va[1]))
                Fc = hinge_frame_2d((w["x0"], 0.0), (1.0, 0.0))
                ins = min(0.5 * tab, 0.3 * w["L"])
                tp = [(w["x0"], 0.0), (w["x0"] + w["L"], 0.0),
                      (w["x0"] + w["L"] - ins, -tab), (w["x0"] + ins, -tab)]
                T = Hp @ rot_y(math.pi) @ Fc.inverted()
                pa = model.panels[page].asm
                model.add(Panel(f"{pname}.Tab", w["piece"], "tab", [tp],
                                (lambda t, pa=pa, T=T: pa(t) @ T), page, None,
                                f"{lab}: {pc['label']} tab"))

    # tabs where pieces meet: glued flat on the other piece's wall
    tref = 90.0
    for pc in pieces:
        ns = pc["nodes"]
        for end in ("first", "last"):
            if pc.get(end) is None:
                continue
            wn, node = pc[end]
            W = walls[wn]
            k = 0 if end == "first" else len(ns) - 2
            w = walls[f"{pc['key']}{k}"]
            xe = w["x0"] if end == "first" else w["x0"] + w["L"]
            out = -1.0 if end == "first" else 1.0
            h = min(w["h"], W["h"])
            c0 = min(plan.clear.get(node, 0.0), h - 3.0)
            ins = min(0.3 * tab, 0.2 * (h - c0))
            tp = [(xe, c0), (xe + out * tab, c0 + ins), (xe + out * tab, h - ins), (xe, h)]
            xw = W["x0"] if node == W["a"] else W["x0"] + W["L"]
            Hp = hinge_frame_2d((xw, 0.0), (0.0, 1.0))
            Fc = hinge_frame_2d((xe, 0.0), (0.0, 1.0))
            best = None
            for phi in (0.0, math.pi):
                T = Hp @ rot_y(phi) @ Fc.inverted()
                cx = (T @ Vector((xe + out * 0.5 * tab, 0.5 * h, 0.0))).x
                inside = W["x0"] - 1e-6 <= cx <= W["x0"] + W["L"] + 1e-6
                if inside and best is None:
                    best = T
            if best is None:
                best = Hp @ rot_y(math.pi) @ Fc.inverted()
            wa = model.panels[f"{base}.{wn}"].asm
            model.add(Panel(f"{base}.{pc['key']}.{end}Tab", w["piece"], "tab", [tp],
                            (lambda t, wa=wa, T=best: wa(t) @ T), f"{base}.{wn}", None,
                            f"{lab}: {pc['label']} tab"))
    return walls
