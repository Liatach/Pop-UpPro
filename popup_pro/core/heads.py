"""Animal face: a mirrored low-poly mesh on the card's fold, cut and
flattened like papercraft, that crushes flat as the card closes.

The design is the face at the host's full opening, built from landmarks in
the mirror plane (forehead, nose, muzzle and chin, down the middle) and a
few points round its edge (the ear hinges, the cheek, the mouth). Every
vertex lies on the edge of each half, so each half unfolds flat without
cuts; the halves are one piece, joined along the nose crease C (between the
eyes) and stuck together by tabs along the forehead, muzzle and chin seams.

How it moves: C and the two ear hinges all meet at one point up the fold
(P), so the face works as a V-fold whose halves are the planes through C
and each ear hinge. Each half's mesh rides on its plane; as the card closes
the mirror plane swings down towards the half plane, and the mesh is
sheared with it (the half plane kept as it is, the mirror plane's
directions carried onto the mirror plane): so C, the ear hinges and the
seams stay exact at every opening, the halves meet along their seams, and
shut, the face lies pressed flat. In between the card is taken as crushed
(the facets stretch a little), as real card would be.
"""

import math

from mathutils import Matrix, Vector

from .base import TAB_LIFT, Panel, Piece
from .geom import ccw, clip_halfplane, frame


def _tri_place(a2, b2, A, B, C, sign):
    """C's place in the pattern, given edge A-B placed at a2-b2: on the side
    that keeps the triangle's turn (sign +1 counter-clockwise)."""
    ab = (B - A).length
    ac = (C - A).length
    bc = (C - B).length
    x = (ac * ac - bc * bc + ab * ab) / (2.0 * ab)
    h = math.sqrt(max(0.0, ac * ac - x * x))
    u = (b2 - a2).normalized()
    v = Vector((-u.y, u.x))
    return a2 + x * u + sign * h * v


def _refl2(p, q):
    """Reflection (4x4, z kept) across the pattern line p-q."""
    d = (q - p).normalized()
    R = Matrix(((2 * d.x * d.x - 1, 2 * d.x * d.y, 0, 0),
                (2 * d.x * d.y, 2 * d.y * d.y - 1, 0, 0),
                (0, 0, 1, 0), (0, 0, 0, 1)))
    T = Matrix.Translation((p.x, p.y, 0.0))
    return T @ R @ T.inverted()


class Heads:
    def _head(self, m, host):
        uid, lab = m["uid"], m["label"]
        if not host.is_spine:
            self.warn(f"{lab}: stands on the card's fold only; skipped")
            return
        yN = float(m["y"])
        W = max(10.0, float(m.get("width", 70.0)))
        h = max(5.0, float(m.get("height", 30.0)))
        Lf = max(0.0, float(m.get("head_brow", 15.0)))
        Ln = max(2.0, float(m.get("head_nose", 25.0)))
        Lm = max(1.0, float(m.get("head_muzzle", 12.0)))
        Lc = max(0.0, float(m.get("head_chin", 12.0)))
        mw = max(0.0, float(m.get("mouth_w", 8.0)))
        md = max(0.0, float(m.get("mouth_d", 12.0)))
        ma = math.radians(float(m.get("mouth_a", 15.0)))
        ec = float(m.get("ear_clock", 10.0))
        eb = max(2.0, float(m.get("ear_base", 18.0)))
        es = max(0.0, float(m.get("ear_size", 22.0)))
        tb = max(2.0, float(m.get("tab", 8.0)))

        # ---- the design, the card open flat (whatever it opens to): x across (the left
        # half at x < 0), y up the fold, z off the card
        def P3(x, y, z):
            return Vector((x, y, z))

        # down the middle, each landmark at its own slope (flattened if it
        # would reach under the card): the nose crease rising to the tip, the
        # forehead falling back to the top of the head, the muzzle dropping
        # steeply from the tip, the chin falling back under
        zlow = 0.12 * h
        warn = []

        def run(frm, L, deg, back):
            """frm + L along a slope deg below level, up the fold (back) or
            down it; the slope eased so it ends no lower than zlow."""
            if L <= 0.5:
                return frm.copy()
            sn = math.sin(math.radians(deg))
            if frm.z - L * sn < zlow:
                sn = max(0.0, (frm.z - zlow) / L)
            cs = math.sqrt(max(0.0, 1.0 - sn * sn))
            return frm + L * P3(0.0, cs if back else -cs, -sn)

        sg = math.radians(15.0)  # (C's rise towards the nose)
        N = P3(0.0, yN, h)
        B = N + Ln * P3(0.0, math.cos(sg), -math.sin(sg))
        if B.z < 0.25 * h:
            warn.append("the nose crease is too long for the snout height (or the snout "
                        "too low)")
        T = run(B, Lf, 40.0, True)
        M = run(N, Lm, 60.0, False)
        K = run(M, Lc, 40.0, False)
        brow, chin = Lf > 0.5, Lc > 0.5
        top = T if brow else B
        bot = K if chin else M
        yc = 0.5 * (top.y + bot.y)
        # P: C carried on up the fold to the card (the V-fold's point, for the
        # first guess at each opening)
        cdir = (B - N).normalized()
        if cdir.z >= -1e-6:
            self.warn(f"{lab}: the nose crease doesn't come down to the card; skipped")
            return
        Pp = N + (-N.z / cdir.z) * cdir
        # ---- the outline: an ellipse round the face on the card, its corners
        # at o'clock round it (12 at the top of the head, 6 at the chin)
        ea_, eb_ = 0.5 * W, max(5.0, 0.5 * (top.y - bot.y))

        def at(hr, z=None):
            """The outline's point at hr o'clock (the left side: 7 to 11)."""
            th_ = math.radians((12.0 - hr) * 30.0)
            return P3(-ea_ * math.sin(th_), yc + eb_ * math.cos(th_), zlow if z is None else z)

        def tangent(hr):
            th_ = math.radians((12.0 - hr) * 30.0)
            return Vector((-ea_ * math.cos(th_), -eb_ * math.sin(th_), 0.0)).normalized()

        # the ear: its hinge along the outline at Ears At, glued down on the card
        ec = max(7.0, min(11.5, ec))
        Ec = at(ec, 0.0)
        tg = tangent(ec)  # (round the face: from its upper end to its lower)
        Ea, Eb = Ec - 0.5 * eb * tg, Ec + 0.5 * eb * tg
        hrs = {}
        for k, v in (("Ea", Ea), ("Eb", Eb)):
            th_ = math.atan2(-v.x / ea_, (v.y - yc) / eb_)
            hrs[k] = 12.0 - math.degrees(th_) / 30.0
        if hrs["Ea"] > 11.8 or hrs["Eb"] < 6.8:
            warn.append("the ears' hinges run past the top of the head or the chin: shorten "
                        "them or move them round")
        # the mouth: a slot cut up from the lower edge beside the chin, its
        # tip the mouth's corner; Mouth Angle leans it out (a smile) or in
        mh = 6.6  # (o'clock: the slot's opening, just beside the chin)
        Em = at(mh)
        dt_ = math.degrees(mw / max(1.0, ea_)) / 30.0  # (hours either side for Mouth Width)
        Co, Jc = at(mh + 0.5 * dt_), at(mh - 0.5 * dt_)
        dv = Vector((-math.sin(ma), math.cos(ma)))  # (up the face, leant out by Mouth Angle)
        Mi = Em + md * P3(dv.x, dv.y, 0.0)
        deep = Mi.x > -2.0
        Mi.x = min(Mi.x, -2.0)
        Mi.z = zlow + 0.25 * (min(M.z, N.z) - zlow)
        if deep or Jc.x > -1.0 or Mi.y > N.y or md < 0.5:
            warn.append("the mouth runs past the chin, the cheek or the nose: make it "
                        "narrower, shallower or less tilted")
        # round the rest of the outline: the forehead's edge, the cheek, the jowl
        ha, hb = hrs["Ea"], hrs["Eb"]
        jw = max(mh + dt_ + 0.4, min(7.4, hb - 0.4))
        outline = [("F1", at(12.0 - (12.0 - ha) / 3.0)), ("F2", at(12.0 - 2.0 * (12.0 - ha) / 3.0)),
                   ("Ea", Ea), ("Eb", Eb), ("Q1", at(hb - (hb - jw) / 3.0)),
                   ("Q2", at(hb - 2.0 * (hb - jw) / 3.0)), ("Jw", at(jw)), ("Co", Co),
                   ("Mi", Mi), ("Jc", Jc)]
        # down the middle: the seams' own corners too (they may bend in the
        # pattern; C, between the eyes, can't)
        mid = []
        if brow:
            Fm = 0.5 * (T + B) + P3(0.0, 0.0, 0.12 * Lf)
            mid += [("T", T), ("Fm", Fm)]
        mid += [("B", B), ("N", N), ("M", M)]
        if chin:
            mid += [("K", K)]
        # a ring of corners inside: temple, eye, cheekbone, cheek, round an
        # inner ellipse, half way up the face
        ring = []
        for k_, hr in enumerate((10.4, 9.3, 8.2)):
            hr2 = min(hr, ha + 0.2) if k_ == 0 else hr
            p_ = at(hr2)
            q_ = P3(0.55 * p_.x, yc + 0.6 * (p_.y - yc), 0.0)
            # (its height: between the middle's at that level and the edge's)
            ys = sorted(mid, key=lambda kv: abs(kv[1].y - q_.y))[0][1]
            q_.z = zlow + 0.5 * (ys.z - zlow)
            ring.append((f"R{k_ + 1}", q_))
        # (the cheek's corner kept up and out from the mouth's, whichever way
        # the mouth leans)
        q_ = ring[-1][1]
        q_.x = min(q_.x, Mi.x - 0.12 * W)
        q_.y = max(q_.y, Mi.y + 0.1 * (top.y - bot.y))
        V = dict(mid + outline + ring)
        A_ = [k for k, _ in mid]
        O_ = [k for k, _ in outline]
        R_ = [k for k, _ in ring]

        def strip(P_, Q_):
            """Triangles between two chains sharing their first and last
            corners, each step taking the shorter diagonal."""
            out_ = [(P_[0], Q_[1], P_[1])]
            i, j = 1, 1
            while not (i == len(P_) - 2 and j == len(Q_) - 2):
                if i == len(P_) - 2:
                    adv_q = True
                elif j == len(Q_) - 2:
                    adv_q = False
                else:
                    adv_q = (V[P_[i]] - V[Q_[j + 1]]).length <= (V[P_[i + 1]] -
                                                                  V[Q_[j]]).length
                if adv_q:
                    out_.append((P_[i], Q_[j], Q_[j + 1]))
                    j += 1
                else:
                    out_.append((P_[i], Q_[j], P_[i + 1]))
                    i += 1
            out_.append((P_[-2], Q_[-2], P_[-1]))
            return [t_ for t_ in out_ if len(set(t_)) == 3]

        # (the slot's tip joins the ring, so the cheek folds in to the mouth's
        # corner and the chin's edge runs from it to the chin)
        Rc = [A_[0]] + R_ + ["Mi", A_[-1]]
        tris = strip(A_, Rc) + strip([A_[0]] + R_ + ["Mi"], [A_[0]] + O_[:O_.index("Mi") + 1]) \
            + [("Mi", "Jc", A_[-1])]
        # the ring's corners lie where the card round each is flat (its angles
        # adding to a whole turn), so it all unfolds without cuts: each moved
        # up or down off the card till it is
        inc = {r_: [t_ for t_ in tris if r_ in t_] for r_ in R_}

        def turn(r_):
            tot = 0.0
            for t_ in inc[r_]:
                o_ = [k for k in t_ if k != r_]
                tot += (V[o_[0]] - V[r_]).angle(V[o_[1]] - V[r_], 0.0)
            return tot

        z_init = {r_: V[r_].z for r_ in R_}

        def flat_z(r_):
            """The height off the card nearest its first guess where r_'s
            corner lies flat."""
            zs = [zlow + (1.5 * h - zlow) * q / 60.0 for q in range(61)]
            fs = []
            for zz in zs:
                V[r_].z = zz
                fs.append(turn(r_) - 2.0 * math.pi)
            cands = sorted((q for q in range(1, 61) if fs[q - 1] * fs[q] <= 0),
                           key=lambda q: abs(zs[q] - z_init[r_]))
            for q in cands[:1]:
                if True:
                    lo, hi, f_lo = zs[q - 1], zs[q], fs[q - 1]
                    for _b in range(40):
                        zm = 0.5 * (lo + hi)
                        V[r_].z = zm
                        fm = turn(r_) - 2.0 * math.pi
                        if fm * f_lo > 0:
                            lo, f_lo = zm, fm
                        else:
                            hi = zm
                    return 0.5 * (lo + hi)
            return None

        # then all together, each moved as little as it can be (any way) till
        # every one lies flat
        import numpy as np
        xv = np.array([c for r_ in R_ for c in V[r_]])
        x00 = xv.copy()

        def fres(xx):
            for k_, r_ in enumerate(R_):
                V[r_].x, V[r_].y, V[r_].z = xx[3 * k_:3 * k_ + 3]
            return np.array([turn(r_) - 2.0 * math.pi for r_ in R_])

        for it_ in range(80):
            lam_ = 0.02 if it_ < 20 else 0.0
            f0 = fres(xv)
            if float(np.abs(f0).max()) < 1e-7:
                break
            Jn = np.zeros((len(R_), len(xv)))
            for c in range(len(xv)):
                dx = np.zeros(len(xv))
                dx[c] = 1e-4
                Jn[:, c] = (fres(xv + dx) - f0) / 1e-4
            if lam_ > 0:
                Ja = np.vstack([Jn, lam_ * np.eye(len(xv))])
                ra = np.concatenate([f0, lam_ * (xv - x00)])
            else:
                Ja, ra = Jn, f0  # (the least move that flattens them)
            stp = np.linalg.lstsq(Ja, -ra, rcond=None)[0]
            mx = float(np.abs(stp).max())
            if mx > 0.1 * W:
                stp *= 0.1 * W / mx
            xv = xv + stp
            for k_ in range(len(R_)):  # (kept off the card)
                xv[3 * k_ + 2] = max(xv[3 * k_ + 2], zlow)
        fres(xv)
        flat_err = max(abs(turn(r_) - 2.0 * math.pi) for r_ in R_)
        if flat_err > math.radians(0.5):
            warn.append("the face's inner corners can't all lie flat: its pattern won't quite "
                        "close (try other landmarks)")
        for w in warn:
            self.warn(f"{lab}: {w}")
        # each turned to face out (away from the card under the face)
        inner = P3(0.0, yc, -0.5 * h)
        out = []
        for a_, b_, c_ in tris:
            A3, B3, C3 = V[a_], V[b_], V[c_]
            n_ = (B3 - A3).cross(C3 - A3)
            if n_.length < 1e-6:
                self.warn(f"{lab}: a facet has folded to nothing ({a_}, {b_}, {c_}); skipped")
                return
            if n_.dot((A3 + B3 + C3) / 3.0 - inner) < 0:
                a_, b_ = b_, a_
            out.append((a_, b_, c_))
        tris = out
        # (seen from above, none folds over another)
        for i_, (a_, b_, c_) in enumerate(tris):
            sa = (V[b_] - V[a_]).to_2d().cross((V[c_] - V[a_]).to_2d())
            if i_ == 0:
                s0 = sa
            elif sa * s0 <= 0:
                self.warn(f"{lab}: the face folds over itself at {a_}, {b_}, {c_}: change "
                          f"the mouth or the ears")
                return
        u1 = (at(9.0, 0.0) - Pp).normalized()  # (the guess's half plane)
        # ---- unfold the left half from C: B-N up the middle of the pattern
        L_BN = (B - N).length
        p2 = {"N": Vector((0.0, 0.0)), "B": Vector((0.0, L_BN))}
        seed = next(i for i, t_ in enumerate(tris) if "B" in t_ and "N" in t_)
        order = [seed]
        placed = {seed}

        def place(i):
            a_, b_, c_ = tris[i]
            ks = [k for k in (a_, b_, c_) if k in p2]
            new = [k for k in (a_, b_, c_) if k not in p2]
            if len(ks) < 2:
                return False
            if not new:
                return True
            k0, k1 = [k for k in (a_, b_, c_) if k in p2][:2]
            # (the turn kept: k0, k1, new in the triangle's own order?)
            cyc = (a_, b_, c_)
            i0 = cyc.index(k0)
            fwd = cyc[(i0 + 1) % 3] == k1
            p2[new[0]] = _tri_place(p2[k0], p2[k1], V[k0], V[k1], V[new[0]],
                                    1.0 if fwd else -1.0)
            return True

        place(seed)
        if p2[[k for k in tris[seed] if k not in ("B", "N")][0]].x > 0:
            # (the left half falls on the right: turn C round)
            p2 = {"N": Vector((0.0, L_BN)), "B": Vector((0.0, 0.0))}
            place(seed)
        while len(placed) < len(tris):
            grew = False
            for i in range(len(tris)):
                if i in placed:
                    continue
                if sum(1 for k in tris[i] if k in p2) >= 2:
                    place(i)
                    placed.add(i)
                    order.append(i)
                    grew = True
            if not grew:
                self.warn(f"{lab}: the face's mesh doesn't unfold; skipped")
                return
        # ---- the frames
        X0 = Vector((1.0, 0.0, 0.0))  # (the design's across: mirror plane's normal)
        yh = (N - Pp).normalized()
        xh = -(u1 - u1.dot(yh) * yh).normalized()
        zh = xh.cross(yh)
        F0 = Matrix.Identity(4)
        for i, c_ in enumerate((xh, yh, zh)):
            F0[0][i], F0[1][i], F0[2][i] = c_
        F0[0][3], F0[1][3], F0[2][3] = Pp
        F0i = F0.inverted()
        md0 = yh.cross(X0)
        if md0.z > 0:
            md0 = -md0  # (into the V: down towards the fold)
        d0 = Vector((md0.dot(xh), md0.dot(zh)))
        if abs(d0.y) < 1e-3:
            self.warn(f"{lab}: the face lies flat in its V; skipped")
            return
        a1 = -u1.y  # (u1 = -a1 up the fold + b1 across, into the left page)
        b1 = -u1.x
        cb = math.cos((N - Pp).angle(u1))  # (C to the ear hinge, in the card)
        cache = {}

        def shear(t):
            """World matrix for the left half at opening t (design coords in)."""
            k_ = float(t)
            if k_ in cache:
                return cache[k_]
            S, l, r, Y, nl, nr = host.dirs(t)
            e = l + r
            e = nl.copy() if e.length < 1e-6 else e.normalized()
            kk = max(-1.0, min(1.0, e.dot(l)))
            # C in the mirror plane: c = -cos(g) Y + sin(g) e, its angle to the
            # ear hinge u = -a1 Y + b1 l kept
            R_ = math.hypot(a1, b1 * kk)
            ph = math.atan2(b1 * kk, a1)
            g = ph + math.acos(max(-1.0, min(1.0, cb / max(R_, 1e-9))))
            c = -math.cos(g) * Y + math.sin(g) * e
            u = -a1 * Y + b1 * l
            x_ = -(u - u.dot(c) * c).normalized()
            z_ = x_.cross(c)
            mt = -(e - e.dot(c) * c)
            mt = mt.normalized() if mt.length > 1e-9 else -z_
            dt = Vector((mt.dot(x_), mt.dot(z_)))
            s_ = dt.y / d0.y
            k2 = (dt.x - d0.x) / d0.y
            Sh = Matrix(((1.0, 0.0, k2, 0.0), (0.0, 1.0, 0.0, 0.0), (0.0, 0.0, s_, 0.0),
                         (0.0, 0.0, 0.0, 1.0)))
            Ft = Matrix.Identity(4)
            for i, c3 in enumerate((x_, c, z_)):
                Ft[0][i], Ft[1][i], Ft[2][i] = c3
            Ft[0][3], Ft[1][3], Ft[2][3] = S + Pp.y * Y
            res = Ft @ Sh @ F0i
            # the right half: mirrored at both ends
            nm_ = (l - r)
            nm_ = nm_.normalized() if nm_.length > 1e-9 else nl.cross(Y).normalized()
            Rf = Matrix(((1.0 - 2.0 * nm_.x * nm_.x, -2.0 * nm_.x * nm_.y, -2.0 * nm_.x * nm_.z),
                         (-2.0 * nm_.y * nm_.x, 1.0 - 2.0 * nm_.y * nm_.y, -2.0 * nm_.y * nm_.z),
                         (-2.0 * nm_.z * nm_.x, -2.0 * nm_.z * nm_.y, 1.0 - 2.0 * nm_.z * nm_.z)))
            Rt = Matrix.Translation(S) @ Rf.to_4x4() @ Matrix.Translation(-S)
            res = (res, Rt @ res, Rt)
            if len(cache) > 4096:
                cache.clear()
            cache[k_] = res
            return res

        # ---- crushing: the shear's guess, then each free corner moved to keep
        # every edge as near its length as it can (the triangles stay flat
        # whatever their corners do), C and the ear hinges held exactly, the
        # seams' corners kept on the mirror plane, all clear of the pages
        names_v = sorted(V)
        fixed = {"Ea", "Eb"}  # (glued down: carried round on the left page)
        onmir = set(A_)  # (down the middle: C and the seams)
        PgL = self.panels[host.p1]
        edges = {}
        for t_ in tris:
            for i_ in range(3):
                u_, w_ = t_[i_], t_[(i_ + 1) % 3]
                edges[frozenset((u_, w_))] = (V[u_] - V[w_]).length
        elist = [(tuple(k_), L_) for k_, L_ in edges.items()]
        pose_cache = {}

        def guess(t):
            Wl = shear(t)[0]
            X0 = {v: Wl @ V[v] for v in names_v}
            onpg = PgL.asm(t) @ PgL.asm(180.0).inverted() @ shear(180.0)[0]
            for v in fixed:
                X0[v] = onpg @ V[v]
            return X0

        def pose(t):
            """World positions of the left half's corners at opening t: solved
            in steps down from full open, each from the last (so the card
            crushes the same way every time)."""
            k_ = round(float(t), 6)
            if k_ in pose_cache:
                return pose_cache[k_]
            tm = round(180.0, 6)
            if tm not in pose_cache:
                pose_cache[tm] = guess(tm)
            above = min((q for q in pose_cache if q >= k_), default=tm)
            prev = pose_cache[above]
            cur = above
            while cur > k_ + 1e-9:
                nxt = max(k_, cur - (4.0 if cur > 24.0 else 1.0))
                g = guess(nxt)
                Wp = shear(cur)[0]
                Wn = shear(nxt)[0]
                # (the last pose, carried on by the guess's own change)
                X0 = {v: (Wn @ Wp.inverted() @ prev[v]) if v not in fixed else g[v]
                      for v in names_v}
                prev = self._head_relax(host, nxt, X0, fixed, onmir, elist, Pp.y)
                cur = round(nxt, 6)
                pose_cache[cur] = prev
            if len(pose_cache) > 4096:
                keep = {tm: pose_cache[tm]}
                pose_cache.clear()
                pose_cache.update(keep)
            return pose_cache.get(k_, prev)

        def tri_map(p2a, p2b, p2c, Pa, Pb, Pc):
            """Affine map: pattern triangle (z off it along the normal) to its
            posed corners."""
            e1, e2 = (p2b - p2a).to_3d(), (p2c - p2a).to_3d()
            E1, E2 = Pb - Pa, Pc - Pa
            nn = E1.cross(E2)
            nn = nn.normalized() if nn.length > 1e-12 else Vector((0.0, 0.0, 1.0))
            Sm = Matrix((e1, e2, Vector((0.0, 0.0, 1.0)))).transposed()
            Dm = Matrix((E1, E2, nn)).transposed()
            L3 = Dm @ Sm.inverted()
            Mx = L3.to_4x4()
            Mx.translation = Pa - L3 @ p2a.to_3d()
            return Mx

        # ---- the panels
        piece = f"Head{uid}"
        self.add_piece(Piece(piece, lab, 1 + uid, (0.0, 0.5 * L_BN)))
        Rp = Matrix.Diagonal((-1.0, 1.0, 1.0, 1.0))  # (the pattern's mirror, about C)
        facet = {}
        for k, i in enumerate(order):
            a_, b_, c_ = tris[i]
            A2, B2, C2 = p2[a_], p2[b_], p2[c_]
            for sd in ("L", "R"):
                nm = f"{piece}.{sd}{k + 1}"
                poly = [A2[:], B2[:], C2[:]]
                if sd == "R":
                    poly = [(-q[0], q[1]) for q in poly]

                def asm(t, a_=a_, b_=b_, c_=c_, A2=A2, B2=B2, C2=C2, sd=sd):
                    X = pose(t)
                    Ml = tri_map(A2, B2, C2, X[a_], X[b_], X[c_])
                    if sd == "L":
                        return Ml
                    return shear(t)[2] @ Ml @ Rp

                p_ = self.add(Panel(nm, piece, "panel", [ccw(poly)], asm, host.p1 if sd == "L"
                                    else host.p2, None,
                                    f"{lab}: {'left' if sd == 'L' else 'right'} facet {k + 1}"))
                p_.free = True
                facet[(sd, frozenset((a_, b_, c_)))] = nm
        fid = {i: frozenset(tris[i]) for i in range(len(tris))}
        # creases between facets: mountain where the face turns away
        for i in range(len(tris)):
            for j in range(i + 1, len(tris)):
                sh = fid[i] & fid[j]
                if len(sh) != 2:
                    continue
                oi = next(iter(fid[i] - sh))
                oj = next(iter(fid[j] - sh))
                s0, s1 = [V[k] for k in sh]
                ni = (s1 - s0).cross(V[oi] - s0)
                if ni.dot(V[oi] - inner) < 0:
                    ni = -ni
                kind_ = "mountain" if ni.dot(V[oj] - s0) < 0 else "valley"
                for sd in ("L", "R"):
                    self.fold_kind[frozenset((facet[(sd, fid[i])], facet[(sd, fid[j])]))] = kind_
        # C: the halves' one fold
        ic = next(i for i in range(len(tris)) if {"B", "N"} <= fid[i])
        self.fold_kind[frozenset((facet[("L", fid[ic])], facet[("R", fid[ic])]))] = "mountain"
        # ---- seams down the middle: a tab off the left half under the right
        seams = []
        for k_, (a_, b_) in enumerate(zip(A_, A_[1:])):
            if (a_, b_) == ("B", "N"):
                continue
            nm_s = "forehead" if A_.index(b_) <= A_.index("B") else (
                "muzzle" if a_ == "N" else "chin")
            seams.append((a_, b_, f"{nm_s}{k_ + 1}" if nm_s == "forehead" else nm_s))
        for a_, b_, nm_s in seams:
            if a_ not in V or b_ not in V or (V[a_] - V[b_]).length < 1.0 or \
                    a_ not in p2 or b_ not in p2:
                continue
            i = next((i for i in range(len(tris)) if {a_, b_} <= fid[i]), None)
            if i is None:
                continue
            fl, fr = facet[("L", fid[i])], facet[("R", fid[i])]
            pa, pb = p2[a_], p2[b_]
            Lt = (pb - pa).length
            ev = (pb - pa) / Lt
            o = next(iter(fid[i] - {a_, b_}))
            nv = Vector((-ev.y, ev.x))
            if nv.dot(p2[o] - pa) > 0:
                nv = -nv  # (off the facet)
            w_ = min(tb, 0.4 * Lt)
            ch = min(0.4 * w_, 0.2 * Lt)
            poly = [pa[:], pb[:], (pb + w_ * nv - ch * ev)[:], (pa + w_ * nv + ch * ev)[:]]
            # (kept on the right facet it's glued under: the facet's shape, turned
            # over the seam)
            Rf2 = _refl2(pa, pb)
            land = ccw([(Rf2 @ p2[k].to_3d()).to_2d()[:] for k in tris[i]])
            for k_ in range(3):
                q0, q1 = Vector(land[k_]), Vector(land[(k_ + 1) % 3])
                dd = (q1 - q0).normalized()
                nn = Vector((-dd.y, dd.x))  # (inwards, counter-clockwise)
                poly = clip_halfplane(poly, nn[:], nn.dot(q0) + 0.3)
            if len(poly) < 3:
                continue
            Mt = Matrix.Translation((0.0, 0.0, -TAB_LIFT)) @ Rp @ _refl2(pa, pb) @ \
                Matrix.Diagonal((1.0, 1.0, -1.0, 1.0))
            Pr = self.panels[fr]

            def asm_t(t, Pr=Pr, Mt=Mt):
                return Pr.asm(t) @ Mt

            self.add(Panel(f"{piece}.{nm_s.capitalize()}Tab", piece, "tab", [ccw(poly)], asm_t,
                           fr, None, f"{lab}: {nm_s} tab, under the right half"))
            self.fold_kind[frozenset((fl, f"{piece}.{nm_s.capitalize()}Tab"))] = "mountain"
        # ---- the ears: on each page, off the hinge (their shape is the user's)
        i = next(i for i in range(len(tris)) if {"Ea", "Eb"} <= fid[i])
        pa, pb = p2["Ea"], p2["Eb"]
        ev = (pb - pa).normalized()
        o = next(iter(fid[i] - {"Ea", "Eb"}))
        nv = Vector((-ev.y, ev.x))
        if nv.dot(p2[o] - pa) > 0:
            nv = -nv
        Lb_ = (pb - pa).length
        ear = [pa, pb, pb + 0.6 * es * nv + 0.1 * Lb_ * ev, pa + es * nv + 0.45 * Lb_ * ev,
               pa + 0.6 * es * nv - 0.15 * Lb_ * ev]
        out3 = Vector((-tg.y, tg.x, 0.0))
        if out3.x > 0:
            out3 = -out3  # (out from the face, across the left page)
        Ed = frame(Ea, Eb - Ea, out3) @ frame(pa.to_3d(), (pb - pa).to_3d(),
                                              nv.to_3d()).inverted()
        for sd, pg in (("L", host.p1), ("R", host.p2)):
            Pg = self.panels[pg]
            fix = Pg.asm(180.0).inverted() @ (shear(180.0)[0] if sd == "L" else
                                                  shear(180.0)[1]) @ \
                Matrix.Translation((0.0, 0.0, TAB_LIFT))
            poly = [q[:] for q in ear] if sd == "L" else [(-q[0], q[1]) for q in ear]
            Ms = fix @ (Ed if sd == "L" else Ed @ Rp)
            # (shear(180) is the design itself: the ear sits on its page)

            def asm_e(t, Pa=Pg.asm, Ms=Ms):
                return Pa(t) @ Ms

            self.add(Panel(f"{piece}.Ear{sd}", piece, "tab", [ccw(poly)], asm_e, pg, None,
                           f"{lab}: {'left' if sd == 'L' else 'right'} ear (glued down)"))
            self.fold_kind[frozenset((facet[(sd, fid[i])], f"{piece}.Ear{sd}"))] = "valley"

    def _head_relax(self, host, t, X0, fixed, onmir, elist, yP):
        """Gauss-Newton on the corners' positions: edges kept their length
        (weighted by 1/length), a light pull back to the guess, the mirror
        corners in the mirror plane, every free corner clear of both pages."""
        import numpy as np
        S, l, r, Y, nl, nr = host.dirs(t)
        nm = l - r
        nm = nm.normalized() if nm.length > 1e-9 else nl.cross(Y).normalized()
        wv = nm.cross(Y).normalized()  # (in the mirror plane, square to the fold)
        # page normals into the gap (pointing at the face)
        npl = nl if nl.dot(r) >= 0 else -nl
        npr = nr if nr.dot(l) >= 0 else -nr
        clear = 0.4 * min(1.0, float(t) / 10.0)  # (none left when shut)
        free = [v for v in sorted(X0) if v not in fixed]
        idx, n = {}, 0
        for v in free:
            k_ = 2 if v in onmir else 3
            idx[v] = (n, k_)
            n += k_
        base = {}
        for v in free:
            if v in onmir:
                d = X0[v] - S
                base[v] = np.array([d.dot(Y), d.dot(wv)])
            else:
                base[v] = np.array(X0[v][:])
        x = np.concatenate([base[v] for v in free])
        x0 = x.copy()
        Sv = np.array(S[:])
        Yv, Wv = np.array(Y[:]), np.array(wv[:])
        P0 = {v: np.array(X0[v][:]) for v in X0}
        NL, NR = np.array(npl[:]), np.array(npr[:])

        def pos(xx, v):
            if v not in idx:
                return P0[v], None
            o, k_ = idx[v]
            if k_ == 2:
                return Sv + xx[o] * Yv + xx[o + 1] * Wv, np.stack([Yv, Wv], 1)
            return xx[o:o + 3], np.eye(3)

        lam = 0.03

        def resid(xx):
            rows, J = [], []
            for (a_, b_), L_ in elist:
                pa, Ja = pos(xx, a_)
                pb, Jb = pos(xx, b_)
                d = pa - pb
                ln = float(np.linalg.norm(d))
                if ln < 1e-9:
                    continue
                u = d / ln
                w = 1.0 / math.sqrt(L_)
                rows.append(w * (ln - L_))
                jr = np.zeros(n)
                if Ja is not None:
                    o, k_ = idx[a_]
                    jr[o:o + k_] += w * (u @ Ja)
                if Jb is not None:
                    o, k_ = idx[b_]
                    jr[o:o + k_] -= w * (u @ Jb)
                J.append(jr)
            for v in free:
                pv, Jv = pos(xx, v)
                o, k_ = idx[v]
                for N_ in (NL, NR):
                    dd = float((pv - Sv) @ N_) - clear
                    jr = np.zeros(n)
                    if dd < 0:
                        rows.append(5.0 * dd)
                        jr[o:o + k_] = 5.0 * (N_ @ Jv)
                    else:
                        rows.append(0.0)
                    J.append(jr)
            rows += list(lam * (xx - x0))
            J += list(lam * np.eye(n))
            return np.array(rows), np.array(J)

        # Gauss-Newton (the pull back to the guess damps it)
        for _ in range(40):
            rv, Jm = resid(x)
            step = np.linalg.lstsq(Jm, -rv, rcond=None)[0]
            x = x + step
            if float(np.abs(step).max()) < 1e-5:
                break
        # (and anything still a hair through a page set back on it)
        for v in free:
            o, k_ = idx[v]
            if k_ == 3:
                for N_ in (NL, NR):
                    dd = float((x[o:o + 3] - Sv) @ N_)
                    if dd < 0.0:
                        x[o:o + 3] = x[o:o + 3] - dd * N_
        out = {}
        for v in X0:
            pv, _ = pos(x, v)
            out[v] = Vector(pv.tolist())
        return out
