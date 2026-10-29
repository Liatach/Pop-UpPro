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

from .geom import ccw, hinge_frame_2d, rot_y

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
def expand(lines, to_pattern=None, mirror=None):
    """Lines (dicts kind/pts/mirror, in the mechanism's own coordinates) ->
    [(kind, [(x, y), ...])] in the piece pattern, mirrors added.
    mirror(p) reflects a point; to_pattern(p) maps it onto the pattern."""
    mirror = mirror or (lambda p: (-p[0], p[1]))
    to_pattern = to_pattern or (lambda p: p)
    out = []
    for ln in lines or []:
        pts = [(float(x), float(y)) for x, y in ln.get("pts", [])]
        if len(pts) < 2:
            continue
        kind = ln.get("kind", "CREASE")
        out.append((kind, [to_pattern(q) for q in pts]))
        if ln.get("mirror", True):
            mp = [mirror(q) for q in pts]
            if max(math.hypot(a[0] - b[0], a[1] - b[1]) for a, b in zip(pts, mp)) > 1e-3:
                out.append((kind, [to_pattern(q) for q in mp]))
    return out


def snap(lines, polys):
    """Move line ends within SNAP of an edge or another line onto it, so
    lines that should meet do."""
    segs = []  # (owner, a, b)
    for poly in polys:
        for i in range(len(poly)):
            segs.append((-1, poly[i], poly[(i + 1) % len(poly)]))
    for li, (_, pts) in enumerate(lines):
        for i in range(len(pts) - 1):
            segs.append((li, pts[i], pts[i + 1]))
    out = []
    for li, (kind, pts) in enumerate(lines):
        pts = list(pts)
        for end in (0, -1):
            p = pts[end]
            best = None
            for owner, a, b in segs:
                if owner == li:
                    continue
                q, d = _near_on_seg(p, a, b)
                if d < SNAP and (best is None or d < best[1] - 1e-9):
                    best = (q, d)
            # a corner of the paper close by (the V point, where a fold meets
            # an edge) wins over the nearest point along a line
            corner = None
            for owner, a, b in segs:
                if owner != -1:
                    continue
                for c in (a, b):
                    d = math.hypot(c[0] - p[0], c[1] - p[1])
                    if d < SNAP and (corner is None or d < corner[1]):
                        corner = (c, d)
            if corner is not None:
                best = corner
            if best is not None:
                # run on a hair past what it meets, so the crossing is cut
                # cleanly (a line ending exactly on an edge can slip through)
                q = best[0]
                o = pts[1] if end == 0 else pts[-2]
                dx, dy = q[0] - o[0], q[1] - o[1]
                L = math.hypot(dx, dy)
                if L > 1e-9:
                    q = (q[0] + 0.02 * dx / L, q[1] + 0.02 * dy / L)
                pts[end] = q
        out.append((kind, pts))
    return out


# ------------------------------------------------------------- regions
class Region:
    def __init__(self, idx):
        self.idx = idx
        self.tris = []
        self.panel = None  # the panel it was cut from
        self.links = {}  # other region idx -> [(type, p, q)]  type CREASE / FOLD
        self.polys = []
        self.area = 0.0
        self.joins = set()  # regions across a Join Tab line


def regions(model, names, lines):
    """Split the panels (names) along the lines. Neighbouring regions are
    linked by a CREASE (a line on one panel) or a FOLD (where two panels
    meet and stay together). Returns (regions, unused lines, triangles...)."""
    verts, edges, faces, face_panel = [], [], [], []

    def vid(p):
        verts.append(Vector((p[0], p[1])))
        return len(verts) - 1

    for n in names:
        for poly in model.panels[n].polys:
            faces.append([vid(p) for p in poly])
            face_panel.append(n)
    ekinds = []
    for li, (kind, pts) in enumerate(lines):
        ids = [vid(p) for p in pts]
        for i in range(len(ids) - 1):
            edges.append((ids[i], ids[i + 1]))
            ekinds.append((kind, li))
    vo, eo, fo, ov, oe, of_ = geometry.delaunay_2d_cdt(verts, edges, faces, 1, 1e-4)
    P = [(v.x, v.y) for v in vo]
    ekind = {}
    for e, origs in zip(eo, oe):
        ekind[(min(e), max(e))] = {ekinds[o] for o in origs if o < len(ekinds)}
    tris, tpanel = [], []
    for f, origs in zip(fo, of_):
        if len(f) != 3 or not origs:
            continue
        if abs(_cross(P[f[0]], P[f[1]], P[f[2]])) < 1e-9:
            continue  # a sliver with no area would join regions across a line
        tris.append(f)
        tpanel.append(face_panel[origs[0]])
    by_edge = {}
    for ti, f in enumerate(tris):
        for i in range(3):
            key = (min(f[i], f[(i + 1) % 3]), max(f[i], f[(i + 1) % 3]))
            by_edge.setdefault(key, []).append(ti)
    reg = [-1] * len(tris)
    out = []
    for t0 in range(len(tris)):
        if reg[t0] >= 0:
            continue
        r = Region(len(out))
        r.panel = tpanel[t0]
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
                    if reg[tj] < 0 and tpanel[tj] == r.panel:
                        reg[tj] = r.idx
                        stack.append(tj)
    # which pairs of panels meet in a fold (they stay together when folded)
    T = (model.t_ref, model.t_ref * 4.0 / 9.0)
    M = {(n, t): model.panels[n].asm(t) for n in names for t in T}
    used = set()
    for key, ts in by_edge.items():
        ks = ekind.get(key) or set()
        lis = {li for _, li in ks}
        if len(ts) != 2:
            continue
        ra, rb = out[reg[ts[0]]], out[reg[ts[1]]]
        if ra is rb:
            continue
        p, q = P[key[0]], P[key[1]]
        types = {k for k, _ in ks}
        if lis:
            used |= lis
        if "CUT" in types:
            continue
        if "JOIN" in types:
            ra.joins.add(rb.idx)
            rb.joins.add(ra.idx)
        hinge = sorted(k for k in types if k.startswith("HINGE"))
        if hinge and ra.panel == rb.panel:
            typ = hinge[0]  # a door's hinge: "HINGE:<degrees>"
        elif ra.panel == rb.panel or "JOIN" in types:
            typ = "CREASE"
        else:
            together = all((M[(ra.panel, t)] @ Vector((x, y, 0.0)) -
                            M[(rb.panel, t)] @ Vector((x, y, 0.0))).length < 0.05
                           for t in T for x, y in (p, q))
            if not together:
                continue  # a slit between two panels
            typ = "FOLD"
        ra.links.setdefault(rb.idx, []).append((typ, p, q))
        rb.links.setdefault(ra.idx, []).append((typ, q, p))
    for r in out:
        tri_pts = []
        for ti in r.tris:
            f = list(tris[ti])
            if _cross(P[f[0]], P[f[1]], P[f[2]]) < 0:
                f = f[::-1]
            tri_pts.append(f)
        r.polys = [q for q in ([P[i] for i in poly] for poly in _merge_convex(tri_pts, P))
                   if len(q) >= 3 and abs(_area(q)) > 1e-6]
        r.area = sum(_area(q) for q in r.polys)
        pts = [q for poly in r.polys for q in poly]
        r.where = (sum(q[0] for q in pts) / max(1, len(pts)),
                   sum(q[1] for q in pts) / max(1, len(pts)))
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
    """Regions hinged on creases whose shared edges must meet: their fold
    angles, solved together for each open angle (continued from a reference
    pose so the paper stays on one branch). A member hangs from a placed
    panel or from an earlier member (a chain of creases); every other edge it
    shares is a constraint."""

    def __init__(self, model, members, cons, tgrid, t_ref):
        # members: [(parent, H (mathutils frame), Hi)]  parent: placed panel
        # name, or the index of an earlier member
        # cons: [(i, j, p)]  j: member index, or a placed panel name
        self.m = model
        self.members = members
        self.cons = cons
        self.cache = {}
        self.res = {}
        self.ok = True
        self.torn = False
        self.torn_at = None
        self.n = len(members)
        self.Hn = [_np(H) for _, H, _ in members]
        self.Hin = [_np(Hi) for _, _, Hi in members]
        self.pts = [np.array((c[2][0], c[2][1], 0.0, 1.0)) for c in cons]
        self.pts_b = [np.array((c[3][0], c[3][1], 0.0, 1.0)) if len(c) > 3 else None
                      for c in cons]
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
                if r > 0.5:
                    # the paper can't follow: no point solving the rest
                    self.torn = True
                    self.torn_at = t
                    break
            if self.torn:
                break
        if self.torn:
            T = sorted(self.grid)
        self.T = T
        self.cache.update(self.grid)
        # the paper can't follow (the lines ask for a shape it can't make)
        self.torn = self.torn or max(self.res.values(), default=0.0) > 0.5
        self.budget = 400  # polishing solves between grid points

    # pieces evaluated once per open angle
    def _fixed(self, t):
        base = [_np(self.m.panels[par].asm(t)) if isinstance(par, str) else None
                for par, _, _ in self.members]
        tgt = {}
        for k, c in enumerate(self.cons):
            j = c[1]
            if not isinstance(j, int):
                q = c[3] if len(c) > 3 else c[2]
                w = self.m.panels[j].asm(t) @ Vector((q[0], q[1], 0.0))
                tgt[k] = np.array(w[:], dtype=np.float64)
        return base, tgt

    def _worlds(self, th, base):
        W = []
        for i, (par, _, _) in enumerate(self.members):
            c, s = math.cos(th[i]), math.sin(th[i])
            R = np.array(((c, 0, s, 0), (0, 1, 0, 0), (-s, 0, c, 0), (0, 0, 0, 1.0)))
            P = base[i] if base[i] is not None else W[par]
            W.append(P @ self.Hn[i] @ R @ self.Hin[i])
        return W

    def _res_only(self, th, base, tgt):
        W = self._worlds(th, base)
        out = []
        for k, c in enumerate(self.cons):
            i, j = c[0], c[1]
            wa = W[i] @ self.pts[k]
            pb = self.pts_b[k] if self.pts_b[k] is not None else self.pts[k]
            wb = W[j] @ pb if isinstance(j, int) else tgt[k]
            out.append(wa[:3] - wb[:3])
        return np.concatenate(out)

    def _resid(self, th, Ms, tgt, jac=False):
        r = self._res_only(th, Ms, tgt)
        if not jac:
            return r
        J = np.zeros((len(r), self.n))
        eps = 1e-6
        for i in range(self.n):
            d = np.array(th, dtype=np.float64)
            d[i] += eps
            J[:, i] = (self._res_only(d, Ms, tgt) - r) / eps
        return r, J

    def _newton(self, t, th0, Ms=None, tgt=None, iters=30):
        if Ms is None:
            Ms, tgt = self._fixed(t)
        th = np.array(th0, dtype=np.float64)
        lam = 1e-9
        r, J = self._resid(th, Ms, tgt, True)
        f = r @ r
        for _ in range(iters):
            A = J.T @ J + lam * np.eye(self.n)
            try:
                step = np.linalg.solve(A, -J.T @ r)
            except np.linalg.LinAlgError:
                step = np.linalg.lstsq(A, -J.T @ r, rcond=None)[0]
            th2 = th + step
            r2, J2 = self._resid(th2, Ms, tgt, True)
            f2 = r2 @ r2
            if f2 < f:
                th, r, J, f = th2, r2, J2, f2
                lam *= 0.3
                if np.abs(step).max() < 1e-12 or f < 1e-18:
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
            seeds = [[a, sg * a] for a in vals for sg in (1.0, -1.0)]
            seeds += [[a, b] for a in vals for b in vals if abs(abs(a) - abs(b)) > 1e-9]
        else:
            import itertools
            signs = list(itertools.product((1.0, -1.0), repeat=min(self.n, 6)))
            seeds = [[v * sg[k % len(sg)] for k in range(self.n)] for v in vals[::2] + [
                math.radians(90), math.radians(-90)] for sg in signs]
        found = []
        for k, s in enumerate(seeds):
            if self.n > 2 and len(found) >= 2:
                break
            if self.n == 2 and found and k >= 2 * len(vals):
                break  # the mirror-image seeds found it
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
            import bisect
            T = self.T
            i = max(1, min(len(T) - 1, bisect.bisect_left(T, t)))
            t0, t1 = T[i - 1], T[i]
            f = 0.0 if t1 <= t0 else min(1.0, max(0.0, (t - t0) / (t1 - t0)))
            guess = (1 - f) * self.grid[t0] + f * self.grid[t1]
            th = guess
            if not self.torn and f not in (0.0, 1.0):
                Ms, tgt = self._fixed(t)
                r0 = self._res_only(guess, Ms, tgt)
                if r0 @ r0 > 1e-10 and self.budget > 0:
                    # between grid points the guess is close: polish it a
                    # little, a bounded number of times (keeps sliders live)
                    self.budget -= 1
                    x, r = self._newton(t, guess, Ms, tgt, iters=6)
                    if r < 0.05:
                        th = x
            if len(self.cache) > 4096:
                self.cache = dict(self.grid)
            self.cache[t] = th
        return th


def _depth(model, name):
    d = 0
    while model.panels[name].parent is not None and d < 99:
        name = model.panels[name].parent
        d += 1
    return d


def _roots(model, regs, reg, tris, P, names):
    """The region of each panel that keeps its place: the biggest one
    touching the fold it hangs from (or the biggest, for the pages)."""
    out = {}
    for n in names:
        mine = [r for r in regs if r.panel == n]
        if not mine:
            continue
        p = model.panels[n]
        touch = set()
        if p.parent is not None and p.hinge is not None:
            Fc = p.hinge.Fc
            o = Fc.to_translation().to_2d()
            yv = Fc.to_3x3().col[1].to_2d().normalized()
            xv = Vector((yv.y, -yv.x))
            for k in range(-400, 401):
                for side in (0.05, -0.05):
                    q = o + yv * (0.5 * k) + xv * side
                    if any(_inside(tuple(q), poly) for poly in p.polys):
                        i = find_region(tuple(q), reg, tris, P)
                        if i is not None and regs[i].panel == n:
                            touch.add(i)
        cand = [regs[i] for i in touch] or mine
        out[n] = max(cand, key=lambda r: abs(r.area)).idx
    return out


def build(model, piece, names, lab, lines, base=None):
    """Split a mechanism's panels (names, all on one piece) along its extra
    lines (pattern coordinates) and hang the regions."""
    from .model import Hinge, Panel
    base = base or piece
    lines = [(k, pts) for k, pts in lines if len(pts) >= 2]
    names = [n for n in names if n in model.panels and model.panels[n].polys]
    if not lines or not names:
        return
    lines = snap(lines, [poly for n in names for poly in model.panels[n].polys])
    regs, unused, reg, tris, P = regions(model, names, lines)
    if unused:
        model.warn(f"{lab}: {len(unused)} extra line(s) don't reach an edge, a cut or "
                   f"another line, so they do nothing (draw them right across)")
    # Join Tabs: the part of a Join line nearer the centre fold is a glue tab,
    # glued back to back with its mirror image, so the two parts it hangs from
    # meet along their Join lines (a ridge); the glued pair stands out of the
    # ridge as a fin, halfway between them
    fins, flap_of, twin = set(), {}, {}
    for r in regs:
        for o in r.joins:
            f, g = (r, regs[o]) if abs(r.where[0]) < abs(regs[o].where[0]) else (regs[o], r)
            fins.add(f.idx)
            flap_of[f.idx] = g.idx
    for k in fins:
        f = regs[k]
        g = min((regs[o] for o in fins if o != k),
                key=lambda g: math.hypot(g.where[0] + f.where[0], g.where[1] - f.where[1]),
                default=None)
        if g is None or math.hypot(g.where[0] + f.where[0], g.where[1] - f.where[1]) > 2.0:
            model.warn(f"{lab}: a Join Tab has no mirror image to glue to (turn on Mirror)")
            continue
        twin[k] = g.idx
    for k, kk in twin.items():
        a_, b_ = flap_of[k], flap_of[kk]
        segs = [sg for sg in regs[k].links.get(a_, []) if sg[0] == "CREASE"]
        pts = {q for sg in segs for q in (sg[1], sg[2])}
        regs[a_].links.setdefault(b_, []).extend(("GLUE", q, (-q[0], q[1])) for q in pts)
    roots = _roots(model, regs, reg, tris, P, names)
    panel = {}  # region idx -> panel name it moves with
    merged = {n: [] for n in names}
    for n, k in roots.items():
        panel[k] = n
        merged[n] += regs[k].polys
    new_panels = []

    def crease_parents(r):
        return [(o, segs) for o, segs in r.links.items()
                if o in panel and all(t == "CREASE" for t, _, _ in segs)]

    def fold_nb(r):
        return [o for o, segs in r.links.items() if any(t == "FOLD" for t, _, _ in segs)]

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
    count = sum(1 for n in model.panels if n.startswith(f"{base}.Fold"))
    while True:
        if not pending():
            break
        progress = False
        # cut free of their own panel and joined only across folds: they stay
        # flat with a neighbour (a projection, a battlement, a doorway); the
        # paper on the far side of the other folds is cut
        for r in pending():
            if has_crease(r):
                continue
            nb = [o for o in fold_nb(r) if o in panel]
            if nb:
                o = min(nb, key=lambda o: _depth(model, panel[o]))
                flat(r, panel[o])
                progress = True
        # door flaps: cut free but for one hinge, they swing out of the
        # printed side by their set angle, opening with the card
        for r in pending():
            hs = [(o, sg) for o, segs in r.links.items() for sg in segs
                  if sg[0].startswith("HINGE")]
            if not hs or any(not sg[0].startswith("HINGE")
                             for segs in r.links.values() for sg in segs):
                continue
            hs = [(o, sg) for o, sg in hs if o in panel]
            if not hs:
                continue
            o, (typ, p, q) = max(hs, key=lambda h: math.hypot(h[1][2][0] - h[1][1][0],
                                                              h[1][2][1] - h[1][1][1]))
            ang = math.radians(float(typ.split(":", 1)[1]))
            pname = panel[o]
            H = hinge_frame_2d(p, (q[0] - p[0], q[1] - p[1]))
            Hi = H.inverted()
            w_ = H @ rot_y(0.5) @ Hi @ Vector((r.where[0], r.where[1], 0.0))
            if w_.z < 0:
                ang = -ang
            tm = max(1.0, model.tmax)
            count += 1
            name = f"{base}.Door{count}"

            def asm(t, pa=model.panels[pname].asm, H=H, Hi=Hi, ang=ang, tm=tm):
                # eased in: barely open while the card is nearly shut, so a
                # door near a fold clears the paper closing on it
                s_ = max(0.0, min(1.0, t / tm))
                return pa(t) @ H @ rot_y(ang * s_ * s_) @ Hi

            panel[r.idx] = name
            hg = Hinge(H, H, "TABLE")
            hg.corner_ok = True
            model.add(Panel(name, piece, "panel", r.polys, asm, pname, hg, f"{lab}: door"))
            if pname in model.cut_panels:
                model.cut_panels.add(name)
            new_panels.append(name)
            progress = True
        for r in pending():
            if r.idx in panel or not crease_parents(r):
                continue
            # every unplaced region joined to it by creases or folds turns
            # with it: solved together
            if r.idx in twin:
                continue  # a join tab: placed once the parts it joins are
            grp, seen, stack = [], {r.idx}, [r.idx]
            while stack:
                k = stack.pop()
                grp.append(k)
                for o in regs[k].links:
                    if o not in panel and o not in seen and o not in twin:
                        seen.add(o)
                        stack.append(o)
            # hang each on a crease: from placed paper first, then from those
            # already hung (a chain)
            parent_of, order = {}, []
            changed = True
            while changed:
                changed = False
                for k in grp:
                    if k in parent_of:
                        continue
                    best = None
                    for o, segs in regs[k].links.items():
                        cs = [sg for sg in segs if sg[0] == "CREASE"]
                        if not cs:
                            continue
                        if o in panel:
                            best = (panel[o], cs[0])
                            break
                        if o in parent_of and best is None:
                            best = (("m", o), cs[0])
                    if best is not None:
                        parent_of[k] = best
                        order.append(k)
                        changed = True
            if not order:
                continue
            idx_of = {k: i for i, k in enumerate(order)}
            members = []
            for k in order:
                par, (_, p, q) = parent_of[k]
                H = hinge_frame_2d(p, (q[0] - p[0], q[1] - p[1]))
                members.append((par if isinstance(par, str) else idx_of[par[1]], H,
                                H.inverted()))
            # every other edge they share must stay together
            cons, done = [], set()
            for k in order:
                i = idx_of[k]
                hseg = parent_of[k][1]
                for o, segs in regs[k].links.items():
                    j = idx_of.get(o, panel.get(o))
                    if j is None:
                        continue
                    for sg in segs:
                        if sg is hseg:
                            continue
                        if sg[0] == "GLUE":  # a point on it, on its glued twin
                            key = (frozenset((k, o)), frozenset(((sg[1][0], sg[1][1]),
                                                                (-sg[1][0], sg[1][1]))))
                            if key not in done:
                                done.add(key)
                                cons.append((i, j, sg[1], sg[2]))
                            continue
                        key = (frozenset((k, o)), frozenset((sg[1], sg[2])))
                        if key in done:
                            continue
                        done.add(key)
                        for pt in (sg[1], sg[2]):
                            cons.append((i, j, pt))
            if not cons:
                for k in order:
                    par = parent_of[k][0]
                    flat(regs[k], par if isinstance(par, str) else panel[par[1]],
                         f"{lab}: a crease with nothing pulling it (the part it cuts off "
                         f"doesn't reach a fold) is left flat")
                progress = True
                continue
            G = Group(model, members, cons, model.TABLE_T, model.t_ref)
            if not G.ok:
                for k in order:
                    par = parent_of[k][0]
                    flat(regs[k], par if isinstance(par, str) else panel[par[1]])
                model.warn(f"{lab}: creases with no fold to make (they need a matching "
                           f"crease across the fold: try Mirror; or they lock each other); "
                           f"left flat")
                progress = True
                continue
            if G.torn:
                for k in order:
                    par = parent_of[k][0]
                    flat(regs[k], par if isinstance(par, str) else panel[par[1]])
                if G.torn_at is not None and G.torn_at > model.t_ref:
                    model.warn(f"{lab}: these creases and cuts would tear opened past about "
                               f"{G.torn_at:.0f} degrees (a join tab angled too far, or a "
                               f"ridge tipped past level); left flat")
                else:
                    model.warn(f"{lab}: these creases and cuts make a shape the paper "
                               f"can't fold to (check the cut runs along the fold, and "
                               f"Mirror); left flat")
                progress = True
                continue
            bad = sorted(t for t, res in G.res.items() if res > 0.05)
            if bad:
                model.warn(f"{lab}: the extra folds can't follow the card around "
                           f"{bad[0]:.0f} degrees (the paper would tear)")
            for gi, k in enumerate(order):
                par = parent_of[k][0]
                pname = par if isinstance(par, str) else panel[par[1]]
                count += 1
                name = f"{base}.Fold{count}"
                H, Hi = members[gi][1], members[gi][2]

                def asm(t, pa=model.panels[pname].asm, H=H, Hi=Hi, G=G, gi=gi):
                    return pa(t) @ H @ rot_y(float(G.theta(t)[gi])) @ Hi

                panel[k] = name
                hg = Hinge(H, H, "TABLE")
                hg.corner_ok = True
                model.add(Panel(name, piece, "panel", regs[k].polys, asm, pname, hg,
                                f"{lab}: fold {count}"))
                if pname in model.cut_panels:
                    model.cut_panels.add(name)
                new_panels.append(name)
            progress = True
            force = False
        # join tabs whose two parts are placed: the fin, halfway between them
        for k, kk in twin.items():
            if k in panel or flap_of[k] not in panel or flap_of[kk] not in panel:
                continue
            segs = [sg for sg in regs[k].links.get(flap_of[k], []) if sg[0] == "CREASE"]
            if not segs:
                continue
            _, p, q = segs[0]
            jd = (q[0] - p[0], q[1] - p[1])
            H = hinge_frame_2d(p, jd)
            Hi = H.inverted()
            # in the pattern: across the join line, towards the tab
            ef = Vector((jd[1], -jd[0], 0.0)).normalized()
            if ef.x * (regs[k].where[0] - p[0]) + ef.y * (regs[k].where[1] - p[1]) < 0:
                ef = -ef
            jv = Vector((jd[0], jd[1], 0.0)).normalized()
            pa = model.panels[panel[flap_of[k]]].asm
            pb = model.panels[panel[flap_of[kk]]].asm
            efb = Vector((-ef.x, ef.y, 0.0))

            def asm(t, pa=pa, pb=pb, H=H, Hi=Hi, ef=ef, efb=efb, jv=jv):
                MA, MB = pa(t), pb(t)
                dA = MA.to_3x3() @ -ef
                dB = MB.to_3x3() @ -efb
                m_ = -(dA + dB)
                th = 0.0
                if m_.length > 1e-6:
                    m_.normalize()
                    base_ = MA.to_3x3() @ ef
                    ax = (MA.to_3x3() @ jv).normalized()
                    th = math.atan2(base_.cross(m_).dot(ax), base_.dot(m_))
                    # the frame's Y runs along jv; its rotation is about that
                    if (H.to_3x3() @ Vector((0, 1, 0))).dot(jv) < 0:
                        th = -th
                return MA @ H @ rot_y(th) @ Hi

            count += 1
            name = f"{base}.Fold{count}"
            hg = Hinge(H, H, "TABLE")
            hg.corner_ok = True
            model.add(Panel(name, piece, "panel", regs[k].polys, asm, panel[flap_of[k]], hg,
                            f"{lab}: join tab {count}"))
            panel[k] = name
            new_panels.append(name)
            progress = True
        if not progress:
            if force:
                break
            force = True
    loose = pending()
    if loose:
        model.warn(f"{lab}: {len(loose)} part(s) cut right out by the extra lines are "
                   f"left out (holes)")
    for name, polys in merged.items():
        model.panels[name].polys = [ccw(p) for p in polys
                                    if len(p) >= 3 and abs(_area(p)) > 1e-6]
    return new_panels
