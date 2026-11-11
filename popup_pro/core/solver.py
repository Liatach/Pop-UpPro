"""Turning solved geometry into hinges the rig can follow (linear, tabulated
or an expression in the opening), the closing stop, and lifting glued
pieces by the paper's thickness."""
import math

from mathutils import Matrix, Vector

from .base import T_MIN
from .geom import angle_from_roty, is_roty, v3


class Solver:
    """Hinge solving and paper thickness. Mixed into Model (model.py)."""

    # ---------------------------------------------------------------- hinges
    def rel(self, name, t):
        p = self.panels[name]
        if p.parent is None:
            return p.asm(t)
        return self.panels[p.parent].asm(t).inverted() @ p.asm(t)

    def true_psi(self, name, t):
        p = self.panels[name]
        h = p.hinge
        M = h.Hp.inverted() @ self.rel(name, t) @ h.Fc
        # mathutils works in single precision: half a micron of slack
        if not is_roty(M, 5e-4):
            raise ValueError(f"{name}: fold is not a pure hinge at t={t}")
        return angle_from_roty(M)

    def true_slide(self, name, t):
        p = self.panels[name]
        h = p.hinge
        M = h.Hp.inverted() @ self.rel(name, t) @ h.Fc
        tr = M.to_translation()
        if not is_roty(M.to_3x3().to_4x4(), 1e-4) or abs(angle_from_roty(M)) > 1e-4 \
                or abs(tr.x) > 1e-3 or abs(tr.z) > 1e-3:
            raise ValueError(f"{name}: not a pure slide")
        return tr.y

    TABLE_T = [T_MIN] + [float(d) for d in range(1, 181)]

    def _table_hinge(self, name, h, tol=2e-4):
        """Hinges with no short formula: the solved angle, sampled every
        degree and more finely wherever the curve bends sharply (a crease
        pulling straight), written into the rig as a driver curve."""
        def wrap(d):
            return (d + math.pi) % (2 * math.pi) - math.pi

        cache = {}
        bad = []

        def true(t):
            if t not in cache:
                try:
                    cache[t] = self.true_psi(name, t)
                except ValueError:
                    # the host can't hold this pose (paper would tear there):
                    # follow it as best we can and say so
                    p = self.panels[name]
                    M = h.Hp.inverted() @ self.rel(name, t) @ h.Fc
                    cache[t] = angle_from_roty(M)
                    bad.append(t)
            return cache[t]

        pts = list(self.TABLE_T)
        # extra folds and things on uneven hosts: refine less finely, and stop
        # (with a warning) rather than chase a kink forever
        loose = getattr(h, "corner_ok", False) or getattr(h, "host_bound", False)
        floor = 1.0 / 64 if loose else 1.0 / 512
        budget = 3000 if loose else 10 ** 9
        out = [pts[0]]
        for i in range(len(pts) - 1):
            stack = [(pts[i], pts[i + 1])]
            seg = []
            while stack:
                t0, t1 = stack.pop()
                tm = 0.5 * (t0 + t1)
                v0, v1, vm = true(t0), true(t1), true(tm)
                lin = v0 + 0.5 * wrap(v1 - v0)
                if abs(wrap(vm - lin)) > tol and t1 - t0 > floor and len(cache) < budget:
                    stack.append((tm, t1))
                    stack.append((t0, tm))
                else:
                    seg.append(t1)
            out += seg
        T, V, prev = [], [], None
        for t in sorted(set(out)):
            v = true(t)
            if prev is not None:
                v = prev + wrap(v - prev)
            T.append(t)
            V.append(v)
            prev = v
        h.table = list(zip(T, V))
        import bisect

        def fn(t, T=T, V=V):
            t = max(T[0], min(T[-1], t))
            i = max(0, min(len(T) - 2, bisect.bisect_right(T, t) - 1))
            f = (t - T[i]) / (T[i + 1] - T[i])
            return V[i] + f * (V[i + 1] - V[i])

        h.fn = fn
        h.expr = None
        err = 0.0
        for i in range(len(T) - 1):
            tm = 0.5 * (T[i] + T[i + 1])
            if self.tmax < 180.0 and tm > self.tmax - 0.5:
                continue  # a floor pulling flat at full opening: square-root corner
            if getattr(h, "corner_ok", False) and (tm > self.tmax - 1.5 or tm < 1.5):
                continue  # extra folds pulling flat as the card opens flat or shuts
            err = max(err, abs(wrap(fn(tm) - true(tm))))
        h.check = err
        lab = self.panels[name].label.split(":")[0]
        far = [t for t in bad if t >= 1.0]  # squashed shut: no matter
        if far:
            self.warn(f"{lab}: its fold can't follow the card from about {min(far):.0f} "
                      f"to {max(far):.0f} degrees (the paper would tear)")
        elif err > 2e-3 and not bad and not getattr(h, "kink_ok", False):
            if getattr(h, "host_bound", False) or getattr(h, "corner_ok", False):
                self.warn(f"{lab}: moves unevenly (its host fold kinks); check it in "
                          f"the movement test")
            else:
                raise ValueError(f"{name}: tabulated hinge is off by {err:.2e} rad")

    def _expr_hinge(self, name, h):
        """Hinges written as a formula: EXPR (in the open angle T, degrees),
        PULL (rotation in the flap's Pull p) and SLIDE (distance in mm along
        the bone's Y, in p). The formula's sign and constant offset are fitted
        to the solved geometry, then checked."""
        sph = h.sph
        uid = sph.get("uid")
        if sph["var"] == "t":
            pts = [(t, None) for t in self.samples]
        else:
            pts = [(90.0, q) for q in (0.0, 0.15, 0.35, 0.5, 0.65, 0.85, 1.0)]
        rows = []
        for t, q in pts:
            if q is not None:
                self.pull[uid] = q
            true = self.true_slide(name, t) if h.kind == "SLIDE" else self.true_psi(name, t)
            rows.append((true, sph["fn"](t if q is None else q)))
        if uid is not None:
            self.pull[uid] = 0.0
        wrap = (lambda d: d) if h.kind == "SLIDE" else \
            (lambda d: (d + math.pi) % (2 * math.pi) - math.pi)
        best = None
        for sg in ((1.0,) if h.kind == "SLIDE" else (1.0, -1.0)):
            c = rows[0][0] - sg * rows[0][1]
            err = max(abs(wrap(tv - sg * fv - c)) for tv, fv in rows)
            if best is None or err < best[0]:
                best = (err, sg, c)
        err, sg, c = best
        h.expr = f"{c:.9g}{'+' if sg > 0 else '-'}({sph['expr']})"
        h.fn = lambda x, sg=sg, c=c, f=sph["fn"]: c + sg * f(x)
        h.check = err
        tol = 0.02 if h.kind == "SLIDE" else 2e-3
        if err > tol:
            raise ValueError(f"{name}: driver formula is off by {err:.2e}")

    def solve_hinges(self):
        for name in self.order:
            p = self.panels[name]
            h = p.hinge
            if h is None:
                continue
            if h.kind in ("EXPR", "PULL", "SLIDE"):
                self._expr_hinge(name, h)
                continue
            if h.kind == "TABLE":
                self._table_hinge(name, h)
                continue
            if h.kind == "LINEAR":
                p90, p1 = self.true_psi(name, 90.0), self.true_psi(name, 180.0)
                d = (p1 - p90 + math.pi) % (2 * math.pi) - math.pi
                k1 = round(d / (0.5 * math.pi) * 2) / 2.0  # moves 1:1 or 1:2
                k0 = p1 - k1 * math.pi
                h.expr = f"{k0:.9g}{k1:+.9g}*radians(t)" if abs(k1) > 1e-12 else f"{k0:.9g}"
                h.fn = lambda t, k0=k0, k1=k1: k0 + k1 * math.radians(t)
            else:
                self._spherical(name, p, h)
            err = 0.0
            for s in self._valid_samples(p):
                if h.kind == "SPHERICAL" and s > self.tmax - 0.5 and self.tmax < 180.0:
                    continue  # flat at the stage's full opening: a square-root corner
                d = h.fn(s) - self.true_psi(name, s)
                d = (d + math.pi) % (2 * math.pi) - math.pi
                err = max(err, abs(d))
            h.check = err
            if err > 2e-3:  # 0.002 rad: under 0.1 mm on a 50 mm panel
                raise ValueError(f"{name}: driver formula is off by {err:.2e} rad")

    def _valid_samples(self, p):
        """Angles where the paper can actually follow (no tearing)."""
        if p.hinge.kind != "SPHERICAL":
            return self.samples
        key = p.hinge.sph["key"]
        return [s for s in self.samples if self.crease(key, s)[3]]

    def _spherical(self, name, p, h):
        sph = h.sph
        parent = self.panels[p.parent]
        other = self.panels[sph["other"]]
        uo = Vector((sph["uo"][0], sph["uo"][1], 0))
        Xp, Yp, Zp = (h.Hp.to_3x3().col[i] for i in range(3))

        def dots(t):
            u = parent.asm(t).to_3x3().inverted() @ (other.asm(t).to_3x3() @ uo)
            return Xp.dot(u), Yp.dot(u), Zp.dot(u)

        # each dot product is k0 + k1*cos(t) + k2*sin(t) exactly
        f0, f90, f180 = dots(0.0), dots(90.0), dots(180.0)
        co = []
        for i in range(3):
            k0 = 0.5 * (f0[i] + f180[i])
            k1 = 0.5 * (f0[i] - f180[i])
            k2 = f90[i] - k0
            co.append((k0, k1, k2))
        al, ao, sg = sph["alpha"], sph["alpha_o"], sph["sigma"]
        sa, ca = math.sin(al), math.cos(al)
        A = tuple(sg * sa * k for k in co[0])
        B = tuple(-sg * sa * k for k in co[2])
        D = (math.cos(ao) - ca * co[1][0], -ca * co[1][1], -ca * co[1][2])

        def ev(c, t):
            r = math.radians(max(t, T_MIN))
            return c[0] + c[1] * math.cos(r) + c[2] * math.sin(r)

        def psi(t, s):
            a_, b_, d_ = ev(A, t), ev(B, t), ev(D, t)
            rr = max(math.sqrt(a_ * a_ + b_ * b_), 1e-9)
            return math.atan2(b_, a_) + s * math.acos(max(-1.0, min(1.0, d_ / rr)))

        ok = [x for x in self._valid_samples(p) if x < self.tmax - 1.0] or [180.0]
        t_ref = min(ok, key=lambda x: abs(x - 90.0))
        ref = self.true_psi(name, t_ref)
        s = min((1.0, -1.0), key=lambda s: abs(
            (psi(t_ref, s) - ref + math.pi) % (2 * math.pi) - math.pi))

        # Blender limits driver expressions to 256 characters, so the three
        # linear terms are driven separately (see build.py) and combined here.
        h.parts = dict(A=A, B=B, D=D, s=s)
        sgn = "+" if s > 0 else "-"
        h.expr = f"atan2(b,a){sgn}acos(max(-1,min(1,d/max(sqrt(a*a+b*b),1e-9))))"
        h.fn = lambda t, s=s: psi(t, s)

    # ------------------------------------------------------------- display
    LIFT_FROM, LIFT_SPAN = 60.0, 50.0  # degrees before full open; see build.lift

    def lift_fraction(self, t):
        return max(0.0, min(1.0, (t - (self.tmax - self.LIFT_FROM)) / self.LIFT_SPAN))

    def shown(self, name, t):
        """Where the rig shows a panel: its pose, plus the lift of anything
        it hangs from that is raised onto its tabs near flat (display only)."""
        return Matrix.Translation(self.lift_offset(name, t)) @ self.panels[name].asm(t)

    def point(self, name, q, t):
        """Where the rig shows pattern point q of a panel at opening t: as
        shown(), or for a panel that bends (blend) a mix of where the two
        stiff panels either side of it would put it."""
        v = Vector((q[0], q[1], 0.0))
        b = self.blend.get(name)
        if b is None:
            return self.shown(name, t) @ v
        u = self.blend_weight(name, q)
        return (1.0 - u) * (self.shown(b[0], t) @ v) + u * (self.shown(b[1], t) @ v)

    def blend_weight(self, name, q):
        a, b, ya, yb = self.blend[name][:4]
        Mw = self.blend[name][4] if len(self.blend[name]) > 4 else None
        y = q[1] if Mw is None else (Mw @ Vector((q[0], q[1], 0.0))).y
        s = max(0.0, min(1.0, (y - ya) / (yb - ya)))
        return s * s * (3.0 - 2.0 * s)  # (eases in at each end: flat at the tip and at G)

    def lift_offset(self, name, t, fraction=None):
        """How far the rig has raised a panel (and so everything hanging
        from it) off where it folds, at opening t (world mm)."""
        f = self.lift_fraction(t) if fraction is None else fraction
        off = Vector((0.0, 0.0, 0.0))
        p = self.panels.get(name)
        while p is not None:
            if p.lift and p.parent:
                d = p.lift_dir if p.lift_dir is not None else Vector((0.0, 0.0, 1.0))
                off += f * p.lift * (self.panels[p.parent].asm(t).to_3x3() @ d)
            p = self.panels.get(p.parent) if p.parent else None
        return off

    def match_lift(self, a, b):
        """Two panels hinged on different parents that meet along a crease
        (a V-fold's halves): when one rides a part the rig raises near flat
        (a strap resting on its tabs) and the other doesn't, raise the other
        by the same, so the crease doesn't open up into a slit."""
        if a not in self.panels or b not in self.panels:
            return
        pa, pb = self.panels[a], self.panels[b]
        ts = [self.tmax - k * self.LIFT_FROM / 4.0 for k in range(5)]

        def local(p, other, t):
            """The lift p needs to sit level with other, in p's parent's frame."""
            d = self.lift_offset(other.parent, t, 1.0) - self.lift_offset(p.parent, t, 1.0)
            return self.panels[p.parent].asm(t).to_3x3().inverted() @ d

        if (local(pa, pb, self.tmax)).length < 1e-6:
            return
        best = None
        # raise the lower half to the higher one's level, or lower the raised
        # one back down (a lift of the opposite sign): whichever needs a lift
        # fixed in that half's own parent's frame, so the rig follows exactly
        for p, q in ((pa, pb), (pb, pa)):
            ds = [local(p, q, t) for t in ts]
            spread = max((d - ds[0]).length for d in ds)
            up = self.lift_offset(q.parent, self.tmax, 1.0).length > \
                self.lift_offset(p.parent, self.tmax, 1.0).length
            score = (spread > 1e-5, not up, spread)
            if best is None or score < best[0]:
                best = (score, p, ds[0])
        _, p, d = best
        p.lift = d.length
        p.lift_dir = d.normalized()

    # --------------------------------------------------------- closing stop
    def close_angle(self, thickness, clearance=0.1, near_spine=8.0, cap=45.0):
        """Smallest open angle (degrees) at which everything folded inside the
        closed card fits between the pages, given the paper thickness (mm).

        Each mechanism panel's closed footprint is mapped onto the page
        (distance from the spine, height); where n layers stack at distance
        u from the spine the pages must be 2 u sin(t/2) >= n * thickness
        apart. Within near_spine of the spine the paper bends instead, so
        those points are ignored."""
        t0 = 0.5
        l, r, nl, nr = self.dirs(t0)
        e = (l + r).normalized()
        foot = []
        for name in self.order:
            p = self.panels[name]
            if p.kind == "page" or p.outside:
                continue
            M = p.asm(t0)
            for poly in p.polys:
                q = [M @ v3(c) for c in poly]
                foot.append([(w.dot(e), w.y) for w in q])
        if not foot:
            return 0.0

        def inside(pt, poly):
            sgn = 0
            for i in range(len(poly)):
                a, b = poly[i], poly[(i + 1) % len(poly)]
                cr = (b[0] - a[0]) * (pt[1] - a[1]) - (b[1] - a[1]) * (pt[0] - a[0])
                if abs(cr) < 1e-9:
                    continue
                s_ = 1 if cr > 0 else -1
                if sgn and s_ != sgn:
                    return False
                sgn = s_
            return True

        need = 0.0
        for poly in foot:
            cx = sum(c[0] for c in poly) / len(poly)
            cy = sum(c[1] for c in poly) / len(poly)
            pts = [(cx, cy)] + [(cx + 0.95 * (c[0] - cx), cy + 0.95 * (c[1] - cy)) for c in poly]
            for pt in pts:
                u = pt[0]
                if u < near_spine:
                    continue
                n = sum(1 for f in foot if inside(pt, f))
                ang = 2 * math.degrees(math.asin(min(1.0, (n * thickness + clearance) / (2 * u))))
                need = max(need, ang)
        return min(need, cap)
