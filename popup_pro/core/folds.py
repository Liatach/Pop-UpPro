"""Extra creases and cuts drawn on a piece (Birmingham mechanisms 5, 6, 9, 10).

A V-fold piece can carry extra fold lines and cuts. The lines split each half
into regions; every region that isn't glued down hangs from a neighbour:

* across a crease on its own side: it turns about that crease. Its share of
  the centre fold must still meet the matching region on the other side, so
  the two turn together (a reverse fold, a step, a jaw) - solved numerically
  and written into the rig as a tabulated driver;
* only across the centre fold (a cut that starts and ends on the centre line,
  with the fold not scored between): it stays flat with the other half and
  juts out past the fold (a projection).

Lines are given in the piece's own pattern: x across the piece (the centre
fold at x = 0), y up the centre fold from the V point. Mirror copies a line
onto the other half (x -> -x).
"""

import math

import numpy as np
from mathutils import Vector, geometry

from .geom import hinge_frame_2d, rot_y

SNAP = 1.5  # mm: line ends this close to another line or edge are moved onto it
TRIVIAL = 0.02  # rad: a solution this close to "everything flat" is the unfolded one


# ------------------------------------------------------------- 2D helpers
def _inside(pt, poly):
    x, y = pt
    c = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            c = not c
    return c


def _near_on_seg(p, a, b):
    ax, ay = a
    dx, dy = b[0] - ax, b[1] - ay
    L2 = dx * dx + dy * dy
    s = 0.0 if L2 < 1e-12 else max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / L2))
    q = (ax + s * dx, ay + s * dy)
    return q, math.hypot(p[0] - q[0], p[1] - q[1])


def _cross(o, a, b):
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def _convex(poly):
    n = len(poly)
    return all(_cross(poly[i], poly[(i + 1) % n], poly[(i + 2) % n]) > -1e-9 for i in range(n))


def _merge_convex(tris, P):
    """Greedily merge CCW triangles (vertex indices into P) sharing edges into
    convex polygons."""
    polys = [list(t) for t in tris]
    changed = True
    while changed:
        changed = False
        for i in range(len(polys)):
            a = polys[i]
            ea = {(a[k], a[(k + 1) % len(a)]): k for k in range(len(a))}
            for j in range(i + 1, len(polys)):
                b = polys[j]
                for kb in range(len(b)):
                    u, v = b[kb], b[(kb + 1) % len(b)]
                    ka = ea.get((v, u))
                    if ka is None:
                        continue
                    # a: ... v(ka) u(ka+1) ... ; splice b's other vertices in between
                    rest = [b[(kb + 2 + m) % len(b)] for m in range(len(b) - 2)]
                    m_ = a[:ka + 1] + rest + a[ka + 1:]
                    # drop collinear points
                    out = []
                    for q in range(len(m_)):
                        if abs(_cross(P[m_[q - 1]], P[m_[q]], P[m_[(q + 1) % len(m_)]])) > 1e-9:
                            out.append(m_[q])
                    if len(out) >= 3 and _convex([P[i] for i in out]):
                        polys[i] = out
                        del polys[j]
                        changed = True
                        break
                if changed:
                    break
            if changed:
                break
    return polys


# ------------------------------------------------------------- lines
def expand(lines):
    """Lines (dicts kind/pts/mirror) -> [(kind, [(x, y), ...])] with mirrors."""
    out = []
    for ln in lines or []:
        pts = [(float(x), float(y)) for x, y in ln.get("pts", [])]
        if len(pts) < 2:
            continue
        kind = ln.get("kind", "CREASE")
        out.append((kind, pts))
        if ln.get("mirror", True) and max(abs(x) for x, _ in pts) > 1e-3:
            out.append((kind, [(-x, y) for x, y in pts]))
    return out


def snap(lines, outline, centre):
    """Move line ends within SNAP of the centre fold, the outline or another
    line onto it, so lines that should meet do."""
    segs = []  # (owner, a, b)
    for k, poly in enumerate(outline):
        for i in range(len(poly)):
            segs.append((-1 - k, poly[i], poly[(i + 1) % len(poly)]))
    segs.append((-99, centre[0], centre[1]))
    for li, (_, pts) in enumerate(lines):
        for i in range(len(pts) - 1):
            segs.append((li, pts[i], pts[i + 1]))
    out = []
    for li, (kind, pts) in enumerate(lines):
        pts = list(pts)
        for end in (0, -1):
            p = pts[end]
            if abs(p[0]) < SNAP and centre[0][1] - SNAP <= p[1] <= centre[1][1] + SNAP:
                pts[end] = (0.0, min(max(p[1], centre[0][1]), centre[1][1]))
                continue
            best = None
            for owner, a, b in segs:
                if owner == li:
                    continue
                q, d = _near_on_seg(p, a, b)
                if d < SNAP and (best is None or d < best[1]):
                    best = (q, d)
            if best is not None:
                pts[end] = best[0]
        out.append((kind, pts))
    return out


# ------------------------------------------------------------- regions
class Region:
    def __init__(self, idx):
        self.idx = idx
        self.tris = []
        self.side = None  # "L" / "R"
        self.links = {}  # other region idx -> [(type, p, q)]  type CREASE / CENTRE
        self.polys = []
        self.panel = None
        self.used = set()  # line indices that border it


def regions(outline, centre, lines, side_of):
    """Split the outline (list of CCW polygons) along the centre fold and the
    lines. Returns (regions, unused line indices)."""
    verts, edges, kinds = [], [], []

    def vid(p):
        verts.append(Vector(p))
        return len(verts) - 1

    for poly in outline:
        ids = [vid(p) for p in poly]
        for i in range(len(ids)):
            edges.append((ids[i], ids[(i + 1) % len(ids)]))
            kinds.append(("OUT", -1))
    a, b = vid(centre[0]), vid(centre[1])
    edges.append((a, b))
    kinds.append(("CENTRE", -1))
    for li, (kind, pts) in enumerate(lines):
        ids = [vid(p) for p in pts]
        for i in range(len(ids) - 1):
            edges.append((ids[i], ids[i + 1]))
            kinds.append((kind, li))
    faces = []
    for poly in outline:
        k0 = sum(len(p) for p in outline[:outline.index(poly)])
        faces.append(list(range(k0, k0 + len(poly))))
    vo, eo, fo, ov, oe, of_ = geometry.delaunay_2d_cdt(verts, edges, faces, 1, 1e-4)
    P = [(v.x, v.y) for v in vo]
    ekind = {}
    for e, origs in zip(eo, oe):
        key = (min(e), max(e))
        ks = set()
        for o in origs:
            ks.add(kinds[o] if o < len(kinds) else ("OUT", -1))
        ekind[key] = ks
    tris = [f for f in fo if len(f) == 3]
    by_edge = {}
    for ti, f in enumerate(tris):
        for i in range(3):
            key = (min(f[i], f[(i + 1) % 3]), max(f[i], f[(i + 1) % 3]))
            by_edge.setdefault(key, []).append(ti)
    # flood fill across unconstrained edges
    reg = [-1] * len(tris)
    out = []
    for t0 in range(len(tris)):
        if reg[t0] >= 0:
            continue
        r = Region(len(out))
        out.append(r)
        stack = [t0]
        reg[t0] = r.idx
        while stack:
            ti = stack.pop()
            r.tris.append(ti)
            f = tris[ti]
            for i in range(3):
                key = (min(f[i], f[(i + 1) % 3]), max(f[i], f[(i + 1) % 3]))
                if ekind.get(key):
                    continue
                for tj in by_edge[key]:
                    if reg[tj] < 0:
                        reg[tj] = r.idx
                        stack.append(tj)
    used = set()
    for key, ts in by_edge.items():
        ks = ekind.get(key) or set()
        lis = {li for _, li in ks if li >= 0}
        if len(ts) != 2:
            for t in ts:
                out[reg[t]].used |= lis
            continue
        ra, rb = out[reg[ts[0]]], out[reg[ts[1]]]
        if ra is rb:
            continue  # a line ending in open paper: does nothing here
        used |= lis
        ra.used |= lis
        rb.used |= lis
        types = {k for k, _ in ks}
        if "CUT" in types or ("OUT" in types and "CENTRE" not in types):
            continue  # the halves' outlines meet along the centre fold
        typ = "CENTRE" if "CENTRE" in types else "CREASE"
        p, q = P[key[0]], P[key[1]]
        ra.links.setdefault(rb.idx, []).append((typ, p, q))
        rb.links.setdefault(ra.idx, []).append((typ, q, p))
    for r in out:
        tri_pts = []
        for ti in r.tris:
            f = tris[ti]
            pts = [P[i] for i in f]
            if _cross(pts[0], pts[1], pts[2]) < 0:
                f = f[::-1]
            tri_pts.append(list(f))
        r.polys = [[P[i] for i in poly] for poly in _merge_convex(tri_pts, P)]
        big = max((poly for poly in r.polys), key=lambda q: abs(_area(q)))
        c = (sum(x for x, _ in big) / len(big), sum(y for _, y in big) / len(big))
        r.side = side_of(c)
        r.area = sum(_area(q) for q in r.polys)
        r.where = c
    unused = set(range(len(lines))) - used
    return out, unused, reg, tris, P


def _area(poly):
    a = 0.0
    for i in range(len(poly)):
        x0, y0 = poly[i]
        x1, y1 = poly[(i + 1) % len(poly)]
        a += x0 * y1 - x1 * y0
    return 0.5 * a


def find_region(pt, reg, tris, P):
    for ti, f in enumerate(tris):
        a, b, c = (P[i] for i in f)
        d1, d2, d3 = _cross(a, b, pt), _cross(b, c, pt), _cross(c, a, pt)
        if (d1 >= -1e-9 and d2 >= -1e-9 and d3 >= -1e-9) or \
                (d1 <= 1e-9 and d2 <= 1e-9 and d3 <= 1e-9):
            return reg[ti]
    return None


# ------------------------------------------------------------- solving
def _np(M):
    return np.array([[M[i][j] for j in range(4)] for i in range(4)], dtype=np.float64)


class Group:
    """Regions hinged on creases whose centre-fold edges must meet: their
    fold angles, solved for each open angle (continued from a reference
    pose so the paper stays on one branch)."""

    def __init__(self, model, members, cons, tgrid, t_ref):
        # members: [(parent panel name, H (mathutils frame), Hi)]
        # cons: [(i, j, p)]  j: member index, or a panel name (placed)
        self.m = model
        self.members = members
        self.cons = cons
        self.cache = {}
        self.res = {}
        self.ok = True
        self.loc = {}
        for k, (i, j, p) in enumerate(cons):
            Hi = members[i][2]
            self.loc[(k, "a")] = np.array((Hi @ Vector((p[0], p[1], 0.0)))[:], dtype=np.float64)
            if isinstance(j, int):
                Hj = members[j][2]
                self.loc[(k, "b")] = np.array((Hj @ Vector((p[0], p[1], 0.0)))[:],
                                              dtype=np.float64)
        self.n = len(members)
        th = self._seed(t_ref)
        if th is None:
            self.ok = False
            return
        self.grid = {}
        T = sorted(set(tgrid) | {t_ref})
        i0 = T.index(t_ref)
        self.grid[t_ref] = th
        for rng in (range(i0 + 1, len(T)), range(i0 - 1, -1, -1)):
            prev = th
            for i in rng:
                t = T[i]
                x, r = self._newton(t, prev)
                self.grid[t] = x
                self.res[t] = r
                prev = x
        self.T = T
        self.cache.update(self.grid)

    # pieces evaluated once per open angle
    def _fixed(self, t):
        Ms = [_np(self.m.panels[par].asm(t) @ H) for par, H, _ in self.members]
        tgt = {}
        for k, (i, j, p) in enumerate(self.cons):
            if not isinstance(j, int):
                w = self.m.panels[j].asm(t) @ Vector((p[0], p[1], 0.0))
                tgt[k] = np.array(w[:], dtype=np.float64)
        return Ms, tgt

    def _resid(self, th, Ms, tgt, jac=False):
        r, J = [], []
        for k, (i, j, p) in enumerate(self.cons):
            a = self.loc[(k, "a")]
            c, s = math.cos(th[i]), math.sin(th[i])
            la = np.array((a[0] * c, a[1], -a[0] * s, 1.0))
            wa = Ms[i] @ la
            da = Ms[i][:3, :3] @ np.array((-a[0] * s, 0.0, -a[0] * c))
            if isinstance(j, int):
                b = self.loc[(k, "b")]
                c2, s2 = math.cos(th[j]), math.sin(th[j])
                wb = Ms[j] @ np.array((b[0] * c2, b[1], -b[0] * s2, 1.0))
                db = Ms[j][:3, :3] @ np.array((-b[0] * s2, 0.0, -b[0] * c2))
            else:
                wb, db = tgt[k], None
            r.append(wa[:3] - wb[:3])
            if jac:
                row = np.zeros((3, self.n))
                row[:, i] += da
                if db is not None:
                    row[:, j] -= db
                J.append(row)
        r = np.concatenate(r)
        return (r, np.vstack(J)) if jac else r

    def _newton(self, t, th0, Ms=None, tgt=None, iters=30):
        if Ms is None:
            Ms, tgt = self._fixed(t)
        th = np.array(th0, dtype=np.float64)
        lam = 1e-9
        r, J = self._resid(th, Ms, tgt, True)
        f = r @ r
        for _ in range(iters):
            A = J.T @ J + lam * np.eye(self.n)
            step = np.linalg.solve(A, -J.T @ r)
            th2 = th + step
            r2, J2 = self._resid(th2, Ms, tgt, True)
            f2 = r2 @ r2
            if f2 < f:
                th, r, J, f = th2, r2, J2, f2
                lam *= 0.3
                if np.abs(step).max() < 1e-12:
                    break
            else:
                lam *= 10.0
                if lam > 1e6:
                    break
        return th, math.sqrt(f)

    def _seed(self, t):
        Ms, tgt = self._fixed(t)
        vals = [math.radians(a) for a in range(-165, 180, 30)]
        if self.n == 1:
            seeds = [[v] for v in vals]
        elif self.n == 2:
            seeds = [[a, b] for a in vals for b in vals]
        else:
            seeds = [[v] * self.n for v in vals] + \
                [[v * (-1) ** k for k in range(self.n)] for v in vals]
        found = []
        for s in seeds:
            th, res = self._newton(t, s, Ms, tgt, iters=40)
            if res > 1e-3:
                continue
            th = (th + math.pi) % (2 * math.pi) - math.pi
            if np.abs(th).max() < TRIVIAL:
                continue
            if any(np.abs(((th - f + math.pi) % (2 * math.pi)) - math.pi).max() < 1e-3
                   for f in found):
                continue
            found.append(th)
        if not found:
            return None
        # the gentlest way to fold it
        return min(found, key=lambda th: np.abs(th).sum())

    def theta(self, t):
        th = self.cache.get(t)
        if th is None:
            near = min(self.T, key=lambda s: abs(s - t))
            th, _ = self._newton(t, self.grid[near])
            if len(self.cache) > 4096:
                self.cache = dict(self.grid)
            self.cache[t] = th
        return th


def build(model, base, piece, lab, outline, halves, lines, glue):
    """Split a V-fold's halves along its extra lines and hang the regions.

    outline: {"L": poly, "R": poly} pattern polygons of the halves (CCW);
    halves: {"L": panel name, "R": panel name}; glue: {"L": (a, b), ...}
    glue edges of each half (pattern)."""
    from .model import Hinge, Panel
    lines = [(k, pts) for k, pts in lines if len(pts) >= 2]
    if not lines:
        return
    polysL, polysR = outline["L"], outline["R"]
    ys = [q[1] for q in polysL + polysR if abs(q[0]) < 1e-6]
    centre = ((0.0, min(ys)), (0.0, max(ys)))
    lines = snap(lines, [polysL, polysR], centre)

    def side_of(c):
        return "L" if _inside(c, polysL) else "R"

    regs, unused, reg, tris, P = regions([polysL, polysR], centre, lines, side_of)
    if unused:
        model.warn(f"{lab}: {len(unused)} extra line(s) don't reach an edge, a cut or "
                   f"another line, so they do nothing (draw them right across)")
    roots = {"L": set(), "R": set()}
    for s, (a, b) in glue.items():
        for f in (0.1, 0.3, 0.5, 0.7, 0.9):
            pt = (a[0] + f * (b[0] - a[0]), a[1] + f * (b[1] - a[1]) + 0.05)
            k = find_region(pt, reg, tris, P)
            if k is not None and regs[k].side == s:
                roots[s].add(k)
    for s in "LR":
        if not roots[s]:
            model.warn(f"{lab}: a cut runs right along the {'left' if s == 'L' else 'right'} "
                       f"glue edge; extra lines skipped")
            return
    panel = {}
    for s in "LR":
        for k in roots[s]:
            panel[k] = halves[s]
    merged = {halves["L"]: [], halves["R"]: []}
    for s in "LR":
        for k in roots[s]:
            merged[halves[s]] += regs[k].polys
    new_panels = []

    def crease_parents(r):
        return [(o, segs) for o, segs in r.links.items()
                if o in panel and all(t == "CREASE" for t, _, _ in segs)]

    def centre_nb(r):
        return [o for o, segs in r.links.items() if any(t == "CENTRE" for t, _, _ in segs)]

    def has_crease(r):
        return any(t == "CREASE" for segs in r.links.values() for t, _, _ in segs)

    def flat(r, parent_name, why=None):
        panel[r.idx] = parent_name
        merged.setdefault(parent_name, []).extend(r.polys)
        if why:
            model.warn(why)

    def pending():
        return [r for r in regs if r.idx not in panel]

    force = False
    count = 0
    while True:
        todo = pending()
        if not todo:
            break
        progress = False
        # projections: hang only across the centre fold, so stay flat with it
        for r in todo:
            if r.idx in panel or has_crease(r):
                continue
            ys_ = [o for o in centre_nb(r) if o in panel]
            if ys_:
                flat(r, panel[ys_[0]])
                progress = True
        for r in pending():
            if r.idx in panel:
                continue
            cps = crease_parents(r)
            if not cps:
                continue
            # the group of regions that must turn together
            grp, stack, ready = [], [r.idx], True
            seen = {r.idx}
            while stack:
                k = stack.pop()
                grp.append(k)
                for o in centre_nb(regs[k]):
                    if o in panel or o in seen:
                        continue
                    if crease_parents(regs[o]):
                        seen.add(o)
                        stack.append(o)
                    else:
                        ready = False
            if not ready and not force:
                continue
            members, idx_of = [], {}
            for k in grp:
                o, segs = crease_parents(regs[k])[0]
                _, p, q = segs[0]
                d = (q[0] - p[0], q[1] - p[1])
                L = math.hypot(*d)
                straight = all(abs(_cross(p, q, a_)) / L < 0.05 and abs(_cross(p, q, b_)) / L < 0.05
                               for o2, segs2 in crease_parents(regs[k]) for _, a_, b_ in segs2)
                if not straight:
                    flat(regs[k], panel[o], f"{lab}: a region held by creases that don't line up "
                         f"can't fold; left flat")
                    continue
                H = hinge_frame_2d(p, d)
                idx_of[k] = len(members)
                members.append((panel[o], H, H.inverted(), k, o))
            if not members:
                progress = True
                continue
            cons = []
            for k in idx_of:
                for o, segs in regs[k].links.items():
                    for t_, p, q in segs:
                        if t_ != "CENTRE":
                            continue
                        j = idx_of.get(o, panel.get(o))
                        if j is None:
                            continue
                        for pt in (p, q):
                            cons.append((idx_of[k], j, pt))
            if not cons:
                for _, _, _, k, o in members:
                    flat(regs[k], panel[o], f"{lab}: a crease with nothing pulling it "
                         f"(it doesn't reach the centre fold) is left flat")
                progress = True
                continue
            G = Group(model, [mb[:3] for mb in members], cons, model.TABLE_T, model.t_ref)
            if not G.ok:
                for _, _, _, k, o in members:
                    flat(regs[k], panel[o])
                model.warn(f"{lab}: creases with no fold to make on their own (needs a "
                           f"matching crease across the centre fold: try Mirror); left flat")
                progress = True
                continue
            bad = sorted(t for t, res in G.res.items() if res > 0.05)
            if bad:
                model.warn(f"{lab}: the extra folds can't follow the card around "
                           f"{bad[0]:.0f} degrees (the paper would tear)")
            for gi, (par, H, Hi, k, o) in enumerate(members):
                count += 1
                name = f"{base}.Fold{count}"
                parent_asm = model.panels[par].asm

                def asm(t, pa=parent_asm, H=H, Hi=Hi, G=G, gi=gi):
                    return pa(t) @ H @ rot_y(float(G.theta(t)[gi])) @ Hi

                panel[k] = name
                new_panels.append((name, regs[k], par, H, asm))
            for name, rg, par, H, asm in new_panels[len(new_panels) - len(members):]:
                model.add(Panel(name, piece, "panel", rg.polys, asm, par,
                                Hinge(H, H, "TABLE"), f"{lab}: fold {name.rsplit('Fold', 1)[1]}"))
            progress = True
            force = False
        if not progress:
            if force:
                break
            force = True
    loose = pending()
    if loose:
        model.warn(f"{lab}: {len(loose)} part(s) cut loose by the extra lines are left out")
    for name, polys in merged.items():
        model.panels[name].polys = [p for p in polys]
