"""Animal face: a mirrored low-poly mesh on the card's fold, cut and
flattened like papercraft, that crushes flat as the card closes.

The design is the face open flat, built from landmarks in the mirror plane
(forehead, nose, muzzle and chin, down the middle) and an outline round the
face on the card (an ellipse, with the ears' hinges and the mouth on it).
Spokes run from the middle out to the outline and two rings cross them: a
quad grid, like a lampshade, each quad flat. The rings' corners are placed
(as little moved from a smooth dome as they can be) where every quad is flat
and the card round each inner corner lies flat (its angles add to a whole
turn), so each half unfolds without cuts. The mouth is a hole between the
rings, which lets the jaw below it bend its own way.

The two halves are one piece joined along the nose crease C (between the
eyes), stuck together by tabs along the forehead, muzzle and chin seams;
the ears are glued down on the pages. As the card closes, the ears ride
their pages and every other corner follows, solved step by step down from
open flat with every facet kept its shape (fitted as a rigid piece), the
middle's corners on the mirror plane, all clear of the pages, until shut it
lies pressed flat.
"""

import math

from mathutils import Matrix, Quaternion, Vector

from .base import TAB_LIFT, Panel, Piece
from .geom import ccw, clip_halfplane


def _refl2(p, q):
    """Reflection (4x4, z kept) across the pattern line p-q."""
    d = (q - p).normalized()
    R = Matrix(((2 * d.x * d.x - 1, 2 * d.x * d.y, 0, 0),
                (2 * d.x * d.y, 2 * d.y * d.y - 1, 0, 0),
                (0, 0, 1, 0), (0, 0, 0, 1)))
    T = Matrix.Translation((p.x, p.y, 0.0))
    return T @ R @ T.inverted()


def _rigid(P2, X):
    """The rotation and shift (no stretch, no mirror) that best lays the
    pattern points P2 (2D) onto the posed points X (3D)."""
    import numpy as np
    A = np.array([[p[0], p[1], 0.0] for p in P2])
    B = np.array([list(x) for x in X])
    ca, cb = A.mean(0), B.mean(0)
    H = (A - ca).T @ (B - cb)
    U, S_, Vt = np.linalg.svd(H)
    D = np.eye(3)
    if np.linalg.det(Vt.T @ U.T) < 0:
        D[2, 2] = -1.0
    R = Vt.T @ D @ U.T
    t = cb - R @ ca
    M = Matrix.Identity(4)
    for i in range(3):
        for j in range(3):
            M[i][j] = float(R[i, j])
        M[i][3] = float(t[i])
    return M


class Heads:
    def _head(self, m, host):
        uid, lab = m["uid"], m["label"]
        if not host.is_spine:
            self.warn(f"{lab}: stands on the card's fold only; skipped")
            return
        yN = float(m["y"])
        W = max(10.0, float(m.get("width", 70.0)))
        h = max(5.0, float(m.get("height", 25.0)))
        Lf = max(0.0, float(m.get("head_brow", 20.0)))
        Ln = max(2.0, float(m.get("head_nose", 30.0)))
        Lm = max(1.0, float(m.get("head_muzzle", 12.0)))
        Lc = max(0.0, float(m.get("head_chin", 15.0)))
        mw = max(0.0, float(m.get("mouth_w", 14.0)))
        md = max(0.0, float(m.get("mouth_d", 6.0)))
        ma = math.radians(float(m.get("mouth_a", 0.0)))
        jaw = max(1.0, float(m.get("head_jaw", 8.0)))
        ec = float(m.get("ear_clock", 10.0))
        eb = max(2.0, float(m.get("ear_base", 18.0)))
        es = max(0.0, float(m.get("ear_size", 22.0)))
        tb = max(2.0, float(m.get("tab", 8.0)))
        warn = []

        def P3(x, y, z):
            return Vector((x, y, z))

        # ---- down the middle, each landmark at its own slope (eased if it
        # would reach under the card): the nose crease rising to the tip, the
        # forehead falling back to the top of the head, the muzzle dropping
        # steeply from the tip, the chin falling back under
        zlow = 0.12 * h

        def run(frm, L, deg, back):
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
        mid = []
        if brow:
            mid += [("T", T), ("Fm", 0.5 * (T + B) + P3(0.0, 0.0, 0.12 * Lf))]
        # (two corners along C too: the card round each lies flat on C's line,
        # so C stays one straight crease)
        mid += [("B", B), ("C1", B.lerp(N, 1.0 / 3.0)), ("C2", B.lerp(N, 2.0 / 3.0)),
                ("N", N), ("M", M)]
        if chin:
            mid += [("K", K)]
        top, bot = mid[0][1], mid[-1][1]
        yc = 0.5 * (top.y + bot.y)
        cdir = (B - N).normalized()
        if cdir.z >= -1e-6:
            self.warn(f"{lab}: the nose crease doesn't come down to the card; skipped")
            return
        Pp = N + (-N.z / cdir.z) * cdir  # (C carried on to the card: the first guess's V)
        # ---- the outline: an ellipse round the face on the card, at o'clock
        # (12 the top of the head, 6 the chin; this is the left half, 6 to 12)
        ea_, eb_ = 0.5 * W, max(5.0, 0.5 * (top.y - bot.y))

        def at(hr, z=None):
            th_ = math.radians((12.0 - hr) * 30.0)
            return P3(-ea_ * math.sin(th_), yc + eb_ * math.cos(th_), zlow if z is None else z)

        per_hr = (math.pi / 6.0) * 0.5 * (ea_ + eb_)  # (mm round the outline an hour)
        ec = max(7.0, min(11.5, ec))
        dh_e = 0.5 * eb / per_hr
        hEa, hEb = ec + dh_e, ec - dh_e
        if hEa > 11.7 or hEb < 6.9:
            warn.append("the ears' hinges run past the top of the head or the chin: shorten "
                        "them or move them round")
        # the mouth: a hole between the rings, Mouth Width round the face
        # either side of 7 o'clock; Mouth Angle tilts it (a smile lifts its
        # outer corner); Jaw is the mandible below it
        dh_m = 0.5 * mw / per_hr
        hm = min(7.6, 0.5 * (hEb - 0.25 + 6.45))  # (below the ears, above the chin)
        hMo, hMi = hm + dh_m, hm - dh_m  # (its outer and inner corners)
        h0 = min(11.85, max(11.6, hEa + 0.25))  # (the top of the head's spoke)
        hrs = [h0]
        if h0 - hEa > 0.9:  # (one spoke between, round the forehead)
            hrs.append(0.5 * (h0 + hEa))
        hrs += [hEa, hEb]
        span = hEb - (hMo + 0.3)
        nf = max(0, int(math.ceil(span / 0.9)) - 1)
        hrs += [hEb - span * (k + 1) / (nf + 1) for k in range(nf)] if span > 0.6 else []
        has_mouth = mw > 0.5 and md > 0.5
        if has_mouth:
            hrs += [hMo, hMi]
        hrs += [6.2]
        hrs = sorted(set(round(x_, 4) for x_ in hrs), reverse=True)
        if any(b_ - a_ < 0.12 for a_, b_ in zip(hrs[1:], hrs)):
            warn.append("the ears and the mouth crowd each other round the face: make them "
                        "smaller or move the ears up")
        names_m = [k for k, _ in mid]
        MV = dict(mid)
        # (enough spokes for every corner down the middle: the widest gaps
        # round the outline split, away from the ears and the mouth)
        keep_ = {round(hEa, 4), round(hEb, 4)}
        if has_mouth:
            keep_ |= {round(hMo, 4), round(hMi, 4)}
        while len(hrs) < len(names_m) + 1:
            gaps = [(hrs[i_] - hrs[i_ + 1], i_) for i_ in range(len(hrs) - 1)
                    if not (hrs[i_] in keep_ and hrs[i_ + 1] in keep_ and
                            {hrs[i_], hrs[i_ + 1]} <= {round(hEa, 4), round(hEb, 4)}) and
                    not (has_mouth and {hrs[i_], hrs[i_ + 1]} == {round(hMo, 4), round(hMi, 4)})]
            g_, i_ = max(gaps)
            hrs.insert(i_ + 1, round(hrs[i_] - 0.5 * g_, 4))
        OUT = [at(x_, 0.0 if abs(x_ - hEa) < 1e-3 or abs(x_ - hEb) < 1e-3 else None)
               for x_ in hrs]  # (the ears' hinges on the card itself)
        ns = len(OUT)
        iEa, iEb = hrs.index(round(hEa, 4)), hrs.index(round(hEb, 4))
        iMo = hrs.index(round(hMo, 4)) if has_mouth else None
        # each spoke from a corner down the middle, in order top to bottom,
        # every corner at least once, as level with its spoke's end as can be
        nm_ = len(names_m)
        INF = float("inf")
        cost = [[INF] * nm_ for _ in range(ns)]
        back = [[0] * nm_ for _ in range(ns)]
        cost[0][0] = abs(MV[names_m[0]].y - OUT[0].y)
        for i_ in range(1, ns):
            for j_ in range(nm_):
                c_ = abs(MV[names_m[j_]].y - OUT[i_].y)
                if has_mouth and i_ in (iMo, iMo + 1) and names_m[j_] in ("K", "T", "Fm"):
                    c_ += 1e3  # (the mouth's spokes from the muzzle or the nose: long enough)
                best = min((cost[i_ - 1][j_], j_), (cost[i_ - 1][j_ - 1] if j_ else INF, j_ - 1))
                cost[i_][j_] = best[0] + c_
                back[i_][j_] = best[1]
        anc = [None] * ns
        j_ = nm_ - 1
        for i_ in range(ns - 1, -1, -1):
            anc[i_] = names_m[j_]
            j_ = back[i_][j_]
        missing = [k for k in names_m if k not in anc]
        if missing:
            self.warn(f"{lab}: too few spokes for its landmarks; skipped")
            return
        # ---- the rings, at fractions along each spoke (the mouth's own
        # spokes: its hole between them, Jaw below it)
        V = {}
        for k, v in mid:
            V[k] = v.copy()
        for i_, o_ in enumerate(OUT):
            V[f"O{i_}"] = o_
        f1 = [0.4] * ns
        f2 = [0.75] * ns
        for i_ in range(ns):
            Ls = (OUT[i_] - MV[anc[i_]]).length
            if has_mouth and i_ in (iMo, iMo + 1):
                lift = (0.5 * mw * math.tan(ma)) * (1.0 if i_ == iMo else -1.0)
                f2[i_] = 1.0 - (jaw + lift) / Ls
                f1[i_] = f2[i_] - md / Ls
                if f1[i_] < 0.15 or f2[i_] > 0.92:
                    warn.append("the mouth doesn't fit between the middle and the edge: make "
                                "it shallower, or the jaw shorter")
                    f1[i_] = max(0.15, min(f1[i_], 0.6))
                    f2[i_] = min(0.92, max(f2[i_], f1[i_] + 0.1))
        # (the neighbours' rings eased towards the mouth's)
        if has_mouth:
            for i_ in (iMo - 1, iMo + 2):
                if 0 < i_ < ns - 1:
                    src = iMo if i_ < iMo else iMo + 1
                    f1[i_] = 0.5 * (f1[i_] + f1[src])
                    f2[i_] = 0.5 * (f2[i_] + f2[src])
        for i_ in range(ns):
            a_, o_ = MV[anc[i_]], OUT[i_]
            for rk, fr in (("P", f1[i_]), ("Q", f2[i_])):
                p_ = a_.lerp(o_, fr)
                if 0 < i_ < ns - 1:  # (the top and bottom edges stay straight)
                    p_.z += 0.35 * h * math.sin(math.pi * fr)
                V[f"{rk}{i_}"] = p_
        # ---- the faces: three bands of quads between spokes (a triangle where
        # two spokes share their middle corner); the mouth's quad left out
        faces = []
        for i_ in range(ns - 1):
            a0, a1_ = anc[i_], anc[i_ + 1]
            if a0 == a1_:
                faces.append((a0, f"P{i_}", f"P{i_ + 1}"))
            else:
                faces.append((a0, f"P{i_}", f"P{i_ + 1}", a1_))
            if not (has_mouth and i_ == iMo):
                faces.append((f"P{i_}", f"Q{i_}", f"Q{i_ + 1}", f"P{i_ + 1}"))
            faces.append((f"Q{i_}", f"O{i_}", f"O{i_ + 1}", f"Q{i_ + 1}"))
        # the top and bottom edges: the first and last spokes, free; each turned
        # to face out (away from the card under the face)
        inner = P3(0.0, yc, -0.5 * h)

        def nrm(f_):
            c_ = sum((V[k] for k in f_), Vector()) / len(f_)
            n_ = Vector()
            for i_ in range(len(f_)):
                a_, b_ = V[f_[i_]] - c_, V[f_[(i_ + 1) % len(f_)]] - c_
                n_ += a_.cross(b_)
            return n_, c_

        out = []
        for f_ in faces:
            n_, c_ = nrm(f_)
            out.append(f_ if n_.dot(c_ - inner) >= 0 else tuple(reversed(f_)))
        # (each quad split on its shorter diagonal: two triangles, the diagonal
        # left uncreased where they lie near flat)
        diag = set()
        faces = []
        for f_ in out:
            if len(f_) == 3:
                faces.append(f_)
                continue
            a_, b_, c_, d_ = f_
            if (V[a_] - V[c_]).length <= (V[b_] - V[d_]).length:
                faces += [(a_, b_, c_), (a_, c_, d_)]
                diag.add(frozenset((a_, c_)))
            else:
                faces += [(a_, b_, d_), (b_, c_, d_)]
                diag.add(frozenset((b_, d_)))
        # ---- flat card round each inner corner: the rings' corners moved (as
        # little as they can be) till it holds
        import numpy as np
        ring = [k for k in V if k[0] in "PQ" and k[1:] not in ("0", str(ns - 1))]
        bnd = {"P0", "Q0", f"P{ns - 1}", f"Q{ns - 1}"}
        if has_mouth:
            bnd |= {f"P{iMo}", f"P{iMo + 1}", f"Q{iMo}", f"Q{iMo + 1}"}
        interior = [k for k in ring if k not in bnd] + ["C1", "C2"]
        inc = {k: [f_ for f_ in faces if k in f_] for k in interior}
        xv = np.array([c for k in ring for c in V[k]])
        x00 = xv.copy()
        ix = {k: 3 * i_ for i_, k in enumerate(ring)}

        def setx(xx):
            for k in ring:
                o = ix[k]
                V[k] = Vector((xx[o], xx[o + 1], xx[o + 2]))

        def corner_turn(k):
            """The card's turn round corner k (half a turn on C's line)."""
            tot = math.pi if k in ("C1", "C2") else 0.0
            for f_ in inc[k]:
                i_ = f_.index(k)
                a_ = V[f_[i_ - 1]] - V[k]
                b_ = V[f_[(i_ + 1) % len(f_)]] - V[k]
                tot += a_.angle(b_, 0.0)
            return tot

        # (and every edge kept near its first length, so nothing collapses)
        e_all = {}
        for f_ in faces:
            for i_ in range(3):
                u_, w_ = f_[i_], f_[(i_ + 1) % 3]
                if u_ in ring or w_ in ring:
                    e_all[frozenset((u_, w_))] = (V[u_] - V[w_]).length
        e_all = [(tuple(k_), L_) for k_, L_ in e_all.items()]
        ew = [0.3]

        hole = [f"P{iMo}", f"Q{iMo}", f"Q{iMo + 1}", f"P{iMo + 1}"] if has_mouth else []
        inc_h = {k: [f_ for f_ in faces if k in f_] for k in hole}
        perim = sum((V[hole[i_]] - V[hole[i_ - 1]]).length for i_ in range(len(hole))) or 1.0

        def hole_close():
            """The mouth's hole, laid out flat by its corners' angles and its
            sides' lengths, must close (else the ring of card round it won't
            unfold): the gap, and the turn short of a whole one."""
            if not hole:
                return []
            hd, p_ = 0.0, Vector((0.0, 0.0))
            turn_ = 0.0
            for i_ in range(4):
                a_, b_ = hole[i_], hole[(i_ + 1) % 4]
                Lh = (V[b_] - V[a_]).length
                p_ = p_ + Lh * Vector((math.cos(hd), math.sin(hd)))
                tot = 0.0
                for f_ in inc_h[b_]:
                    j_ = f_.index(b_)
                    tot += (V[f_[j_ - 1]] - V[b_]).angle(V[f_[(j_ + 1) % 3]] - V[b_], 0.0)
                ext = math.pi - (2.0 * math.pi - tot)  # (the hole's turn there)
                hd += ext
                turn_ += ext
            err_t = min(abs(turn_ - 2.0 * math.pi), abs(turn_ + 2.0 * math.pi))
            return [p_.x / perim, p_.y / perim, err_t]

        def fres(xx):
            setx(xx)
            r_ = [corner_turn(k) - 2.0 * math.pi for k in interior] + hole_close()
            r_ += [ew[0] * ((V[a_] - V[b_]).length / L_ - 1.0) for (a_, b_), L_ in e_all]
            return np.array(r_)

        def jac(xx, f0):
            Jn = np.zeros((len(f0), len(xx)))
            for c in range(len(xx)):
                dx = np.zeros(len(xx))
                dx[c] = 2e-3  # (mathutils works in single precision)
                Jn[:, c] = (fres(xx + dx) - fres(xx - dx)) / 4e-3
            return Jn

        # (Levenberg-Marquardt, a light pull back to the dome, steps kept only
        # if they help)
        # (Levenberg-Marquardt, a pull back to the dome eased off stage by
        # stage, steps kept only if they help)
        for lam_, ew[0] in ((0.02, 0.3), (0.005, 0.15), (1e-3, 0.08), (1e-4, 0.05), (1e-5, 0.02)):
            mu = 1e-2

            def tot(xx, lam_=lam_):
                f_ = fres(xx)
                return float(f_ @ f_ + lam_ * lam_ * ((xx - x00) @ (xx - x00))), f_

            cost, f0 = tot(xv)
            for it_ in range(80):
                if float(np.abs(f0[:len(interior) + len(hole_close())]).max()) < 1e-6:
                    break
                Jn = jac(xv, f0)
                Ja = np.vstack([Jn, lam_ * np.eye(len(xv))])
                ra = np.concatenate([f0, lam_ * (xv - x00)])
                A = Ja.T @ Ja
                g = Ja.T @ ra
                while True:
                    stp = np.linalg.solve(A + mu * np.diag(np.diag(A) + 1e-12), -g)
                    xn = xv + stp
                    for k in ring:
                        xn[ix[k] + 2] = max(xn[ix[k] + 2], zlow)
                    cn, fn = tot(xn)
                    if cn < cost:
                        xv, cost, f0 = xn, cn, fn
                        mu = max(mu / 3.0, 1e-12)
                        break
                    mu *= 5.0
                    if mu > 1e10:
                        break
                if mu > 1e10:
                    break
        res_ = fres(xv)[:len(interior) + (3 if hole else 0)]
        if float(np.abs(res_).max()) > 1e-2:
            warn.append("the face can't be made of flat pieces that unfold without cuts at "
                        "these landmarks: its pattern won't quite close (try others)")
        for w in warn:
            self.warn(f"{lab}: {w}")
        # (seen from above, no face folds over another)
        s0 = None
        for f_ in faces:
            n_, _ = nrm(f_)
            if s0 is None:
                s0 = n_.z
            elif n_.z * s0 <= 0 and abs(n_.z) > 1e-3 * n_.length:
                self.warn(f"{lab}: the face folds over itself near {', '.join(f_)}: change "
                          f"the mouth or the ears")
                break
        # ---- unfold the left half from C: B-N up the middle of the pattern
        L3 = (B - N).length / 3.0
        p2 = {"C1": Vector((0.0, 0.0)), "B": Vector((0.0, L3))}

        def place(f_):
            """Lay face f_ beside its placed corners (keeping its turn)."""
            ks = [k for k in f_ if k in p2]
            if len(ks) < 2:
                return False
            n_ = len(f_)
            # (two placed corners next to each other round the face)
            for i_ in range(n_):
                a_, b_ = f_[i_], f_[(i_ + 1) % n_]
                if a_ in p2 and b_ in p2:
                    break
            else:
                return False
            A2, B2 = p2[a_], p2[b_]
            A3, B3 = V[a_], V[b_]
            ex = (B3 - A3).normalized()
            n3, _ = nrm(f_)
            ey = n3.normalized().cross(ex)  # (into the face, to the left of a->b)
            u2 = (B2 - A2).normalized()
            v2 = Vector((-u2.y, u2.x))
            for k in f_:
                if k in p2:
                    continue
                d_ = V[k] - A3
                p2[k] = A2 + d_.dot(ex) * u2 + d_.dot(ey) * v2
            return True

        seed = next(f_ for f_ in faces if "B" in f_ and "C1" in f_)
        place(seed)
        if sum(p2[k].x for k in seed) > 0:
            p2 = {"C1": Vector((0.0, L3)), "B": Vector((0.0, 0.0))}
            place(seed)
        done = {seed}
        while len(done) < len(faces):
            grew = False
            for f_ in faces:
                if f_ in done:
                    continue
                if place(f_):
                    done.add(f_)
                    grew = True
            if not grew:
                self.warn(f"{lab}: the face's mesh doesn't unfold; skipped")
                return
        names_v = sorted(V)
        A_ = names_m
        u1 = (at(9.0, 0.0) - Pp).normalized()  # (the first guess's half plane)
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

        # ---- crushing: each corner solved, step by step down from open flat,
        # every face kept its shape, the ears riding their page, the middle's
        # corners on the mirror plane, all clear of the pages
        fixed = {f"O{iEa}", f"O{iEb}"}  # (the ears' hinges: glued down)
        onmir = set(A_)
        PgL = self.panels[host.p1]
        edges = {}
        for f_ in faces:
            for i_ in range(len(f_)):
                for j_ in range(i_ + 1, len(f_)):  # (sides and diagonals: rigid)
                    u_, w_ = f_[i_], f_[j_]
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
            k_ = round(float(t), 6)
            if k_ in pose_cache:
                return pose_cache[k_]
            if 180.0 not in pose_cache:
                pose_cache[180.0] = guess(180.0)
            above = min((q for q in pose_cache if q >= k_), default=180.0)
            prev = pose_cache[above]
            cur = above
            while cur > k_ + 1e-9:
                nxt = max(k_, cur - (4.0 if cur > 24.0 else 1.0))
                g = guess(nxt)
                Wp, Wn = shear(cur)[0], shear(nxt)[0]
                X0 = {v: (Wn @ Wp.inverted() @ prev[v]) if v not in fixed else g[v]
                      for v in names_v}
                prev = self._head_relax(host, nxt, X0, fixed, onmir, elist, Pp.y)
                cur = round(nxt, 6)
                pose_cache[cur] = prev
            return pose_cache.get(k_, prev)

        # ---- the panels: every face fitted as a rigid piece
        piece = f"Head{uid}"
        self.add_piece(Piece(piece, lab, 1 + uid, (0.0, 0.5 * (B - N).length)))
        Rp = Matrix.Diagonal((-1.0, 1.0, 1.0, 1.0))  # (the pattern's mirror, about C)
        facet = {}
        fit_cache = {}
        for k, f_ in enumerate(faces):
            P2 = [p2[q] for q in f_]
            for sd in ("L", "R"):
                nm = f"{piece}.{sd}{k + 1}"
                poly = [q[:] for q in P2] if sd == "L" else [(-q[0], q[1]) for q in P2]

                def asm(t, f_=f_, P2=P2, sd=sd, poly=poly):
                    key = (round(float(t), 6), f_, sd)
                    if key in fit_cache:
                        return fit_cache[key]
                    X = pose(t)
                    pts = [X[q] for q in f_]
                    if sd == "R":
                        Rt = shear(t)[2]
                        pts = [Rt @ q for q in pts]
                    Mx = _rigid(poly, pts)
                    S_, l_, r_, Y_, nl_, nr_ = host.dirs(t)
                    tf = float(t)
                    if tf < 4.0:
                        # (the last few degrees: each facet eased flat onto the
                        # middle, as the pages press it)
                        wgt = max(0.0, min(1.0, (4.0 - tf) / 3.0))
                        nm_ = (l_ - r_)
                        nm_ = nm_.normalized() if nm_.length > 1e-9 else nl_
                        R3 = Mx.to_3x3()
                        nf = R3 @ Vector((0.0, 0.0, 1.0))
                        tgt = nm_ if nf.dot(nm_) >= 0 else -nm_
                        q_ = nf.rotation_difference(tgt)
                        q_ = Quaternion().slerp(q_, wgt)
                        cen = sum((Mx @ Vector((q[0], q[1], 0.0)) for q in poly),
                                  Vector()) / len(poly)
                        cen2 = cen - wgt * (cen - S_).dot(nm_) * nm_
                        Rq = q_.to_matrix().to_4x4()
                        Mx = Matrix.Translation(cen2) @ Rq @ Matrix.Translation(-cen) @ Mx
                    # (a facet fitted a hair through a page set back on it)
                    for N_ in (nl_ if nl_.dot(r_) >= 0 else -nl_,
                               nr_ if nr_.dot(l_) >= 0 else -nr_):
                        lo = min((Mx @ Vector((q[0], q[1], 0.0)) - S_).dot(N_) for q in poly)
                        if lo < 0.0:
                            Mx = Matrix.Translation(-lo * N_) @ Mx
                    if len(fit_cache) > 200000:
                        fit_cache.clear()
                    fit_cache[key] = Mx
                    return Mx

                p_ = self.add(Panel(nm, piece, "panel", [ccw(poly)], asm, host.p1 if sd == "L"
                                    else host.p2, None,
                                    f"{lab}: {'left' if sd == 'L' else 'right'} facet {k + 1}"))
                p_.free = True
                facet[(sd, f_)] = nm
        # creases between faces: mountain where the face turns away, none where
        # they lie flat together
        for i_, fa in enumerate(faces):
            for fb in faces[i_ + 1:]:
                sh = set(fa) & set(fb)
                if len(sh) != 2:
                    continue
                na, ca = nrm(fa)
                nb, cb_ = nrm(fb)
                if frozenset(sh) in diag and \
                        na.normalized().dot(nb.normalized()) > math.cos(math.radians(12.0)):
                    kind_ = "skip"
                else:
                    kind_ = "mountain" if na.dot(cb_ - ca) < 0 else "valley"
                for sd in ("L", "R"):
                    self.fold_kind[frozenset((facet[(sd, fa)], facet[(sd, fb)]))] = kind_
        for f_ in faces:  # (C: the halves' one fold)
            if len({"B", "C1", "C2", "N"} & set(f_)) >= 2:
                self.fold_kind[frozenset((facet[("L", f_)], facet[("R", f_)]))] = "mountain"
        # ---- seams down the middle: a tab off the left half under the right
        for k_, (a_, b_) in enumerate(zip(A_, A_[1:])):
            if a_ in ("B", "C1", "C2") and b_ in ("C1", "C2", "N"):
                continue
            nm_s = ("Forehead" if A_.index(b_) <= A_.index("B") else
                    ("Muzzle" if a_ == "N" else "Chin"))
            f_ = next((f_ for f_ in faces if a_ in f_ and b_ in f_), None)
            if f_ is None or (V[a_] - V[b_]).length < 1.0:
                continue
            pa, pb = p2[a_], p2[b_]
            Lt = (pb - pa).length
            ev = (pb - pa) / Lt
            nv = Vector((-ev.y, ev.x))
            cen = sum((p2[q] for q in f_), Vector((0.0, 0.0))) / len(f_)
            if nv.dot(cen - pa) > 0:
                nv = -nv  # (off the facet)
            w_ = min(tb, 0.4 * Lt)
            ch = min(0.4 * w_, 0.2 * Lt)
            poly = [pa[:], pb[:], (pb + w_ * nv - ch * ev)[:], (pa + w_ * nv + ch * ev)[:]]
            Rf2 = _refl2(pa, pb)
            land = ccw([(Rf2 @ p2[q].to_3d()).to_2d()[:] for q in f_])
            for i_ in range(len(land)):
                q0, q1 = Vector(land[i_]), Vector(land[(i_ + 1) % len(land)])
                dd = (q1 - q0).normalized()
                nn = Vector((-dd.y, dd.x))
                poly = clip_halfplane(poly, nn[:], nn.dot(q0) + 0.3)
            if len(poly) < 3:
                continue
            # (turned over the seam onto the right half's facet, under it)
            Mt = Matrix.Translation((0.0, 0.0, -TAB_LIFT)) @ Rp @ Rf2
            Pr = self.panels[facet[("R", f_)]]

            def asm_t(t, Pr=Pr, Mt=Mt):
                return Pr.asm(t) @ Mt

            tn = f"{piece}.{nm_s}{k_ + 1}Tab"
            self.add(Panel(tn, piece, "tab", [ccw(poly)], asm_t, Pr.name, None,
                           f"{lab}: {nm_s.lower()} tab, under the right half"))
            self.fold_kind[frozenset((facet[("L", f_)], tn))] = "mountain"
        # ---- the ears: glued down on each page off their hinge (their shape
        # is the user's to cut), turned round the face with their clock
        fe = next(f_ for f_ in faces if f"O{iEa}" in f_ and f"O{iEb}" in f_)
        pa, pb = p2[f"O{iEa}"], p2[f"O{iEb}"]
        ev = (pb - pa).normalized()
        nv = Vector((-ev.y, ev.x))
        cen = sum((p2[q] for q in fe), Vector((0.0, 0.0))) / len(fe)
        if nv.dot(cen - pa) > 0:
            nv = -nv
        Lb_ = (pb - pa).length
        ear = [pa, pb, pb + 0.6 * es * nv + 0.1 * Lb_ * ev, pa + es * nv + 0.45 * Lb_ * ev,
               pa + 0.6 * es * nv - 0.15 * Lb_ * ev]
        Ea3, Eb3 = V[f"O{iEa}"], V[f"O{iEb}"]
        tg = (Eb3 - Ea3).normalized()
        out3 = Vector((-tg.y, tg.x, 0.0))
        if out3.dot(Ea3 - P3(0.0, yc, 0.0)) < 0:
            out3 = -out3  # (out from the face, across the left page)
        # (the ear laid on the card: its hinge kept, the rest out across the page)
        Ed = _rigid([pa, pb, pa + nv], [Ea3, Eb3, Ea3 + out3])
        for sd, pg in (("L", host.p1), ("R", host.p2)):
            Pg = self.panels[pg]
            fix = Pg.asm(180.0).inverted() @ (shear(180.0)[0] if sd == "L" else
                                              shear(180.0)[1]) @ \
                Matrix.Translation((0.0, 0.0, TAB_LIFT))
            poly = [q[:] for q in ear] if sd == "L" else [(-q[0], q[1]) for q in ear]
            Ms = fix @ (Ed if sd == "L" else Ed @ Rp)

            def asm_e(t, Pa=Pg.asm, Ms=Ms):
                return Pa(t) @ Ms

            self.add(Panel(f"{piece}.Ear{sd}", piece, "tab", [ccw(poly)], asm_e, pg, None,
                           f"{lab}: {'left' if sd == 'L' else 'right'} ear (glued down)"))
            self.fold_kind[frozenset((facet[(sd, fe)], f"{piece}.Ear{sd}"))] = "valley"

    def _head_relax(self, host, t, X0, fixed, onmir, elist, yP):
        """Gauss-Newton on the corners' positions (all in arrays): edges kept
        their length (weighted by 1/length), a pull back to the guess eased
        off, the mirror corners in the mirror plane, every free corner clear
        of both pages."""
        import numpy as np
        S, l, r, Y, nl, nr = host.dirs(t)
        nm = l - r
        nm = nm.normalized() if nm.length > 1e-9 else nl.cross(Y).normalized()
        wv = nm.cross(Y).normalized()  # (in the mirror plane, square to the fold)
        npl = nl if nl.dot(r) >= 0 else -nl  # (page normals into the gap)
        npr = nr if nr.dot(l) >= 0 else -nr
        clear = 0.4 * min(1.0, float(t) / 10.0)  # (none left when shut)
        names = sorted(X0)
        vi = {v: i for i, v in enumerate(names)}
        nv = len(names)
        Sv = np.array(S[:])
        Yv, Wv = np.array(Y[:]), np.array(wv[:])
        # each corner: its place = c0 + B @ (its own few unknowns)
        Bm = np.zeros((nv, 3, 3))
        c0 = np.zeros((nv, 3))
        off = np.zeros(nv, dtype=int)
        kk = np.zeros(nv, dtype=int)
        x0 = []
        n = 0
        for i, v in enumerate(names):
            P = np.array(X0[v][:])
            if v in fixed:
                c0[i] = P
                kk[i] = 0
            elif v in onmir:
                c0[i] = Sv
                Bm[i, :, 0], Bm[i, :, 1] = Yv, Wv
                kk[i] = 2
                d = P - Sv
                x0 += [d @ Yv, d @ Wv]
            else:
                Bm[i] = np.eye(3)
                kk[i] = 3
                x0 += list(P)
            off[i] = n
            n += kk[i]
        x0 = np.array(x0)
        x = x0.copy()
        ea = np.array([vi[a_] for (a_, b_), _ in elist])
        eb = np.array([vi[b_] for (a_, b_), _ in elist])
        L0 = np.array([L_ for _, L_ in elist])
        w = 1.0 / np.sqrt(L0)
        NL, NR = np.array(npl[:]), np.array(npr[:])
        freei = np.array([i for i in range(nv) if kk[i] > 0])
        G = np.zeros((3 * nv, n))  # (each corner's place against the unknowns)
        for i in freei:
            G[3 * i:3 * i + 3, off[i]:off[i] + kk[i]] = Bm[i, :, :kk[i]]
        c0f = c0.reshape(-1)
        E = len(elist)
        rowsE = np.repeat(np.arange(E), 3)
        colA = (3 * ea[:, None] + np.arange(3)[None, :]).reshape(-1)
        colB = (3 * eb[:, None] + np.arange(3)[None, :]).reshape(-1)
        NN = np.stack([NL, NR])

        def resid(xx, lam):
            P = (c0f + G @ xx).reshape(nv, 3)
            d = P[ea] - P[eb]
            ln = np.maximum(np.linalg.norm(d, axis=1), 1e-9)
            u = d / ln[:, None]
            r1 = w * (ln - L0)
            Jp = np.zeros((E, 3 * nv))
            wu = (w[:, None] * u).reshape(-1)
            np.add.at(Jp, (rowsE, colA), wu)
            np.add.at(Jp, (rowsE, colB), -wu)
            # (the pages: only those corners through them count)
            dd = (P - Sv) @ NN.T - clear  # (nv x 2)
            hit = (dd < 0) & (kk[:, None] > 0)
            ii, jj = np.nonzero(hit)
            r2 = 5.0 * dd[ii, jj]
            Jq = np.zeros((len(ii), 3 * nv))
            for q, (i, j) in enumerate(zip(ii, jj)):
                Jq[q, 3 * i:3 * i + 3] = 5.0 * NN[j]
            rv = np.concatenate([r1, r2, lam * (xx - x0)])
            Jm = np.vstack([Jp @ G, Jq @ G, lam * np.eye(n)])
            return rv, Jm

        def places(xx):
            return (c0f + G @ xx).reshape(nv, 3)

        for lam in (0.03, 0.005):
            for _ in range(40):
                rv, Jm = resid(x, lam)
                step = np.linalg.solve(Jm.T @ Jm, -(Jm.T @ rv))  # (the pull keeps it square)
                mx = float(np.abs(step).max())
                if mx > 3.0:
                    step *= 3.0 / mx
                x = x + step
                if mx < 1e-4:
                    break
            x0 = x.copy()
        P = places(x)
        # (anything still a hair through a page set back on it)
        for i in freei:
            if kk[i] == 3:
                for N_ in (NL, NR):
                    dd = float((P[i] - Sv) @ N_)
                    if dd < 0.0:
                        P[i] = P[i] - dd * N_
        return {v: Vector(P[vi[v]].tolist()) for v in names}
