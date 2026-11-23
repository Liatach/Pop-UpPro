"""Animal face: a mirrored low-poly mesh on the card's fold, cut and
flattened like papercraft, that crushes flat as the card closes.

The pattern is a hand-made koala's or goblin's (core/koala.py), facet for
facet as its creases were drawn on the flattened card: the nose crease C
up the middle, a band of quads from C out to the ear's hinge, the
forehead's facets round to the top of the head, the muzzle's over the
nose's tip (the koala's; none on the goblin unless asked), and below the
mouth's slot the jaw's three to the chin. Its landmarks
(forehead, nose, muzzle and chin; the mouth's width, lip, angle and jaw;
how far out the ears sit and how big) stretch the pieces of that pattern.

The two halves are one piece joined along C, stuck together by tabs along
the forehead, muzzle and chin seams; the ears are glued down on the pages.
Open flat the face stands up from its pattern with every facet kept its
shape, the seams and C in the mirror plane, the ears' hinges on the card;
as the card closes the ears ride their pages and every other corner
follows, solved step by step down from open flat, until shut it lies
pressed flat.
"""


from mathutils import Matrix, Quaternion, Vector

from .base import TAB_LIFT, Panel, Piece
from .geom import ccw, clip_halfplane, poly_area


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

        from . import koala as KO
        uid, lab = m["uid"], m["label"]
        if not host.is_spine:
            self.warn(f"{lab}: stands on the card's fold only; skipped")
            return
        base = m.get("head_base", "KOALA")
        base = base if base in KO.BASES else "KOALA"
        D = KO.DEFAULTS[base]

        def g(k, d, lo):
            return max(lo, float(m.get(k, d)))

        nose = g("head_nose", D["nose"], 5.0)
        brow = g("head_brow", D["brow"], 5.0)
        muzzle = g("head_muzzle", D["muzzle"], 0.0)
        chin = g("head_chin", D["chin"], 2.0)
        mw = g("mouth_w", D["mouth_w"], 2.0)
        md = g("mouth_d", D["mouth_d"], 3.0)
        ma = max(-45.0, min(45.0, float(m.get("mouth_a", 0.0))))
        jaw = g("head_jaw", D["jaw"], 3.0)
        cheek = g("ear_base", D["cheek"], 15.0)
        es = max(0.0, float(m.get("ear_size", D["ear"])))
        tb = max(2.0, float(m.get("tab", 8.0)))
        yN = float(m["y"])
        mo = m.get("mouth_out")
        mdn = m.get("mouth_down")
        p_np, ear_np, topo = KO.pattern(nose, brow, muzzle, chin, mw, md, ma, jaw, cheek, es,
                                        base=base,
                                        mouth_out=None if mo is None else float(mo),
                                        mouth_down=None if mdn is None else float(mdn))
        Xd, err, out_ = KO.stand(p_np, topo)
        if err > 0.02 * nose:
            self.warn(f"{lab}: the face can't stand up from its pattern at these landmarks "
                      f"without stretching (try others)")
        p2 = {k: Vector((float(v[0]), float(v[1]))) for k, v in p_np.items()}
        V = {k: Vector((float(v[0]), float(v[1]), float(v[2]))) for k, v in Xd.items()}
        # (every facet round the same way in the pattern; each quad two
        # triangles across its shorter diagonal, the card bending a little
        # there where it must, its other diagonal a spring keeping it flat)
        faces = []
        soft = set()
        for f_ in topo["faces"]:
            a2 = sum(p2[f_[i]].x * p2[f_[(i + 1) % len(f_)]].y -
                     p2[f_[(i + 1) % len(f_)]].x * p2[f_[i]].y for i in range(len(f_)))
            f_ = tuple(f_) if a2 > 0 else tuple(reversed(f_))
            if len(f_) == 4:
                a_, b_, c_, d_ = f_
                if (p2[a_] - p2[c_]).length <= (p2[b_] - p2[d_]).length:
                    faces += [(a_, b_, c_), (a_, c_, d_)]
                    soft.add(frozenset((b_, d_)))
                else:
                    faces += [(a_, b_, d_), (b_, c_, d_)]
                    soft.add(frozenset((a_, c_)))
            else:
                faces.append(f_)

        def nrm(f_):
            n_ = Vector()
            for i in range(len(f_)):
                a_, b_ = V[f_[i]], V[f_[(i + 1) % len(f_)]]
                n_ += Vector(((a_.y - b_.y) * (a_.z + b_.z), (a_.z - b_.z) * (a_.x + b_.x),
                              (a_.x - b_.x) * (a_.y + b_.y)))
            return n_, sum((V[q] for q in f_), Vector()) / len(f_)

        # (seen from above, no facet folds over another)
        s0 = None
        for f_ in faces:
            n_, _ = nrm(f_)
            if s0 is None:
                s0 = n_.z
            elif n_.z * s0 <= 0 and abs(n_.z) > 0.6 * n_.length:  # (a jaw may tuck under)
                self.warn(f"{lab}: the face folds over itself: try other landmarks")
                break
        # ---- the frame round the middle at each opening: across (the left
        # page at minus), along the fold, out of the V
        S9, l9, r9, Y9, nl9, nr9 = host.dirs(179.0)
        up180 = (l9 + r9).normalized()
        y0 = yN - 0.5 * (V["S"].y + V["E"].y)  # ("Nose At": C's middle)
        mcache = {}

        def mframe(t):
            k_ = float(t)
            if k_ in mcache:
                return mcache[k_]
            S, l, r, Y, nl, nr = host.dirs(t)
            e = l + r
            e = up180.copy() if e.length < 1e-6 else e.normalized()
            ax = r - l
            ax = ax.normalized() if ax.length > 1e-9 else -l
            M_ = Matrix.Identity(4)
            for i, c_ in enumerate((ax, Y, e)):
                M_[0][i], M_[1][i], M_[2][i] = c_
            M_[0][3], M_[1][3], M_[2][3] = S + y0 * Y
            Rf = Matrix.Identity(3) - 2.0 * Matrix((ax * ax.x, ax * ax.y, ax * ax.z)).transposed()
            Rt = Matrix.Translation(S) @ Rf.to_4x4() @ Matrix.Translation(-S)
            if len(mcache) > 4096:
                mcache.clear()
            mcache[k_] = (M_, Rt)
            return M_, Rt

        names_v = sorted(V)
        W180 = {v: mframe(180.0)[0] @ V[v] for v in names_v}
        fixed = set(topo["hinge"])
        onmir = set(topo["mirror"])
        side = set(names_v) - onmir
        PgL = self.panels[host.p1]
        elist = [((a_, b_), L_, 1.0)
                 for (a_, b_), L_ in KO.edges(p_np, topo["faces"]).items()]
        # (the seams stay ridges: each facet off a seam keeps falling away
        # from it towards the card, as it does open, never caving in)
        convex = []
        for _, a_, b_ in topo["seams"]:
            u_ = (W180[b_] - W180[a_]).normalized()
            w_ = up180 - up180.dot(u_) * u_
            for f_ in topo["faces"]:
                if a_ in f_ and b_ in f_:
                    for c_ in f_:
                        if c_ in (a_, b_):
                            continue
                        d_ = (W180[c_] - W180[a_]).dot(w_)
                        hh = ((W180[c_] - W180[a_]) - (W180[c_] - W180[a_]).dot(u_) * u_).length
                        convex.append((a_, b_, c_, -1.0 if d_ < 0.0 else 1.0, 0.05 * hh))
        # (every crease held lightly to its fold open flat, as creased card
        # springs back, let go towards shut where the pages press it flat:
        # the shapes the facets alone leave free go the way card would)
        import numpy as np
        crs = KO.creases(p_np, topo["faces"])
        nmz = list(Xd)
        vz = {k: i for i, k in enumerate(nmz)}
        Pz = np.array([Xd[k] for k in nmz])
        ph180 = KO.fold_angles(Pz, tuple(np.array([vz[c[k]] for c in crs]) for k in range(4)) +
                               (np.array([c[4] for c in crs]),), out_)
        springs = (crs, out_, ph180)
        pose_cache = {180.0: W180}

        def grid_below(g):
            return round(g - (4.0 if g > 24.0 + 1e-9 else 1.0), 6)

        def solve(g):
            """The pose at a step of the solve: every 4 degrees down to 24,
            then every degree (stepped down to from the nearest above)."""
            if g in pose_cache:
                return pose_cache[g]
            cur = min(q for q in pose_cache if q >= g and q in gset)
            prev = pose_cache[cur]
            while cur > g + 1e-9:
                nxt = grid_below(cur)
                Mn = mframe(nxt)[0] @ mframe(cur)[0].inverted()
                onpg = PgL.asm(nxt) @ PgL.asm(180.0).inverted()
                X0 = {v: (onpg @ W180[v]) if v in fixed else (Mn @ prev[v]) for v in names_v}
                prev = self._head_relax(host, nxt, X0, fixed, onmir, elist, side, convex,
                                         springs)
                cur = nxt
                pose_cache[cur] = prev
            return prev

        gset = {180.0}
        g_ = 180.0
        while g_ > 0.0:
            g_ = grid_below(g_)
            gset.add(max(0.0, g_))
        ipose = {}

        def pose(t):
            k_ = round(min(180.0, max(0.0, float(t))), 6)
            if k_ in gset:
                return solve(k_)
            if k_ in ipose:
                return ipose[k_]
            # (between steps: each corner carried round with the middle,
            # part way from one step's pose to the next; the ears' hinges
            # exactly on their page)
            hi_ = min(q for q in gset if q > k_)
            lo_ = max(q for q in gset if q < k_)
            a_ = (k_ - lo_) / (hi_ - lo_)
            Xl, Xh = solve(lo_), solve(hi_)
            Ml, Mh, Mk = mframe(lo_)[0], mframe(hi_)[0], mframe(k_)[0]
            Mli, Mhi = Ml.inverted(), Mh.inverted()
            onpg = PgL.asm(k_) @ PgL.asm(180.0).inverted()
            out_p = {}
            for v in names_v:
                if v in fixed:
                    out_p[v] = onpg @ W180[v]
                else:
                    out_p[v] = Mk @ ((Mli @ Xl[v]).lerp(Mhi @ Xh[v], a_))
            if len(ipose) > 4096:
                ipose.clear()
            ipose[k_] = out_p
            return out_p

        # ---- the panels: every facet fitted as a rigid piece
        piece = f"Head{uid}"
        self.add_piece(Piece(piece, lab, 1 + uid, (0.0, 0.5 * (p2["S"].y + p2["E"].y))))
        Rp = Matrix.Diagonal((-1.0, 1.0, 1.0, 1.0))  # (the pattern's mirror, about C)
        facet = {}
        fit_cache = {}
        for k, f_ in enumerate(faces):
            P2 = [p2[q] for q in f_]
            for sd in ("L", "R"):
                nm = f"{piece}.{sd}{k + 1}"
                poly = [q[:] for q in P2] if sd == "L" else [(-q[0], q[1]) for q in P2]

                def asm(t, f_=f_, sd=sd, poly=poly):
                    key = (round(float(t), 6), f_, sd)
                    if key in fit_cache:
                        return fit_cache[key]
                    X = pose(t)
                    pts = [X[q] for q in f_]
                    if sd == "R":
                        Rt = mframe(t)[1]
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
                        if tf > 179.0:
                            N_ = up180
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
        # creases between facets: mountain where the face turns away from its
        # neighbour, valley where it turns towards it
        for i_, fa in enumerate(faces):
            for fb in faces[i_ + 1:]:
                if len(set(fa) & set(fb)) != 2:
                    continue
                na, ca = nrm(fa)
                nb, cb_ = nrm(fb)
                kind_ = "mountain" if na.dot(cb_ - ca) < 0 else "valley"
                if frozenset(set(fa) ^ set(fb)) in soft:
                    kind_ = "skip"  # (a quad's own diagonal: no crease)
                for sd in ("L", "R"):
                    self.fold_kind[frozenset((facet[(sd, fa)], facet[(sd, fb)]))] = kind_
        for a_, b_ in topo["c_edges"]:  # (C: the halves' one fold)
            f_ = next(f_ for f_ in faces if a_ in f_ and b_ in f_)
            self.fold_kind[frozenset((facet[("L", f_)], facet[("R", f_)]))] = "mountain"
        # ---- seams down the middle: a tab off the left half under the right
        for k_, (nm_s, a_, b_) in enumerate(topo["seams"]):
            f_ = next((f_ for f_ in faces if a_ in f_ and b_ in f_), None)
            if f_ is None or (p2[a_] - p2[b_]).length < 1.0:
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
            # (trimmed clear of every other facet laid out, both halves)
            obst = [[p2[q][:] for q in fo] for fo in faces if fo != f_] + \
                [[(-p2[q].x, p2[q].y) for q in fo] for fo in faces]
            for ob in obst:
                land = ccw(ob)
                best = None
                for i_ in range(len(land)):
                    q0, q1 = Vector(land[i_]), Vector(land[(i_ + 1) % len(land)])
                    dd = (q1 - q0).normalized()
                    nn = Vector((-dd.y, dd.x))
                    c_ = clip_halfplane(poly, (-nn)[:], -nn.dot(q0) + 0.3)
                    if len(c_) < 3:
                        continue
                    # (rather one that leaves the most of the tab's fold)
                    keep = 0.0
                    for j_ in range(len(c_)):
                        u0, u1 = Vector(c_[j_]), Vector(c_[(j_ + 1) % len(c_)])
                        if max(abs((u_ - pa).dot(nv)) for u_ in (u0, u1)) < 1e-3:
                            keep += (u1 - u0).length
                    sc_ = (round(keep, 1), abs(poly_area(c_)))
                    if best is None or sc_ > best[0]:
                        best = (sc_, c_)
                best = None if best is None else best[1]
                if best is None:
                    poly = []
                    break
                poly = best
            if len(poly) < 3 or abs(poly_area(poly)) < 0.1 * w_ * Lt:
                continue
            # (and clear of the right half's facet it's glued under)
            land = ccw([(Rf2 @ p2[q].to_3d()).to_2d()[:] for q in f_])
            for i_ in range(len(land)):
                q0, q1 = Vector(land[i_]), Vector(land[(i_ + 1) % len(land)])
                if max(abs((q_ - pa).dot(nv)) for q_ in (q0, q1)) < 1e-3:
                    continue  # (the seam itself: the tab's fold)
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
        # ---- the ears: glued down on each page off their hinge (the koala's
        # ear, its depth set; its shape is the user's to cut)
        if es > 0.5:
            pa, pb = p2["H0"], p2["B2"]
            ear = [pa, pb] + [Vector((float(q[0]), float(q[1]))) for q in ear_np]
            ev = (pb - pa).normalized()
            nv = Vector((-ev.y, ev.x))
            if nv.dot(p2["S"] - pa) > 0:
                nv = -nv
            Ea3, Eb3 = W180["H0"], W180["B2"]
            tg = (Eb3 - Ea3).normalized()
            out3 = up180.cross(tg).normalized()
            if out3.dot(Ea3 - W180["S"]) < 0:
                out3 = -out3  # (out from the face, across the left page)
            Ed = _rigid([pa, pb, pa + nv],
                        [Ea3 + TAB_LIFT * up180, Eb3 + TAB_LIFT * up180,
                         Ea3 + TAB_LIFT * up180 + out3])
            Rt180 = mframe(180.0)[1]
            hinge_f = [f_ for f_ in faces if len({"H0", "B1", "B2"} & set(f_)) == 2]
            for sd, pg in (("L", host.p1), ("R", host.p2)):
                Pg = self.panels[pg]
                fix = Pg.asm(180.0).inverted() @ (Ed if sd == "L" else Rt180 @ Ed @ Rp)
                poly = [q[:] for q in ear] if sd == "L" else [(-q[0], q[1]) for q in ear]

                def asm_e(t, Pa=Pg.asm, fix=fix):
                    return Pa(t) @ fix

                en = f"{piece}.Ear{sd}"
                self.add(Panel(en, piece, "tab", [ccw(poly)], asm_e, pg, None,
                               f"{lab}: {'left' if sd == 'L' else 'right'} ear (glued down)"))
                for f_ in hinge_f:
                    self.fold_kind[frozenset((facet[(sd, f_)], en))] = "valley"

    def _head_relax(self, host, t, X0, fixed, onmir, elist, side, convex=(), springs=()):
        """Gauss-Newton on the corners' positions (all in arrays): edges kept
        their length (weighted by 1/length), a pull back to the guess eased
        off, the mirror corners in the mirror plane, every free corner clear
        of both pages, and the side corners on their own side of the middle."""
        import numpy as np
        S, l, r, Y, nl, nr = host.dirs(t)
        nm = l - r
        nm = nm.normalized() if nm.length > 1e-9 else nl.cross(Y).normalized()
        wv = nm.cross(Y).normalized()  # (in the mirror plane, square to the fold)
        ev_ = l + r  # (out of the V)
        ev_ = ev_.normalized() if ev_.length > 1e-9 else nl
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
        ea = np.array([vi[a_] for (a_, b_), _, _ in elist])
        eb = np.array([vi[b_] for (a_, b_), _, _ in elist])
        L0 = np.array([L_ for _, L_, _ in elist])
        w = np.array([k_ for _, _, k_ in elist]) / np.sqrt(L0)
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
        NM = np.array(nm[:])  # (the mirror's normal, towards the left page)
        NN = np.stack([NL, NR, NM])
        sidev = np.array([v in side and v not in fixed for v in names])
        from . import koala as KO
        if springs:
            crs, sout, sph = springs
            cidx = tuple(np.array([vi[c[k]] for c in crs]) for k in range(4)) + \
                (np.array([c[4] for c in crs]),)

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
            dd = (P - Sv) @ NN.T - clear  # (nv x 3)
            hit = (dd < 0) & (kk[:, None] > 0)
            hit[:, 2] &= sidev
            ii, jj = np.nonzero(hit)
            r2 = 5.0 * dd[ii, jj]
            Jq = np.zeros((len(ii), 3 * nv))
            for q, (i, j) in enumerate(zip(ii, jj)):
                Jq[q, 3 * i:3 * i + 3] = 5.0 * NN[j]
            # (each seam's facets falling away from it: only those caving in count)
            r3, Jc = [], []
            Ev = np.array(ev_[:])
            for a_, b_, c_, sg_, m_ in convex:
                ia, ib, ic = vi[a_], vi[b_], vi[c_]
                u_ = P[ib] - P[ia]
                u_ = u_ / max(np.linalg.norm(u_), 1e-9)
                w_ = Ev - (Ev @ u_) * u_
                w_ = w_ / max(np.linalg.norm(w_), 1e-9)
                g_ = sg_ * ((P[ic] - P[ia]) @ w_) - m_
                if g_ < 0.0:
                    row = np.zeros(3 * nv)
                    row[3 * ic:3 * ic + 3] += 5.0 * sg_ * w_
                    row[3 * ia:3 * ia + 3] -= 5.0 * sg_ * w_
                    r3.append(5.0 * g_)
                    Jc.append(row)
            # (light springs holding every crease to its fold open flat, let
            # go towards shut, where the pages press it flat)
            sk = min(1.0, float(t) / 45.0)
            if springs and sk > 0.0:
                ph = KO.fold_angles(P, cidx, sout)
                Jf = KO.fold_jac(P, cidx, sout)
                wt = 0.1 * sk
                Jr = np.zeros((len(ph), 3 * nv))
                for r_ in range(4):
                    for k in range(3):
                        np.add.at(Jr, (np.arange(len(ph)), 3 * cidx[r_] + k), wt * Jf[:, r_, k])
                r3 += list(wt * (ph - sph))
                Jc += list(Jr)
            r3 = np.array(r3)
            Jc = np.array(Jc).reshape(-1, 3 * nv)
            rv = np.concatenate([r1, r2, r3, lam * (xx - x0)])
            Jm = np.vstack([Jp @ G, Jq @ G, Jc @ G, lam * np.eye(n)])
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
                for N_ in ((NL, NR, NM) if sidev[i] else (NL, NR)):
                    dd = float((P[i] - Sv) @ N_)
                    if dd < 0.0:
                        P[i] = P[i] - dd * N_
        return {v: Vector(P[vi[v]].tolist()) for v in names}
