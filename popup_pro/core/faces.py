"""An animal face on a loop or tube (Birmingham 17, after the curves of 15
and 16): the top edge carries on up past the front crease as a muzzle, folded
back over the loop by a dart.

model.py has the module's overview and the Model class."""
import math

from mathutils import Matrix, Vector

from .base import Panel
from .geom import frame


class Faces:
    """Animal-face builder. Mixed into Model (model.py)."""

    def _tube_face(self, m, piece, P, uc, hgt, nf, wf):
        """A straight loop's or tube's muzzle: off the top of its front
        crease (at uc along its strip)."""
        Gn = min(float(m.get("face_width", 18.0)), wf)
        w1 = wf / nf  # a facet's width
        j = min(nf - 1, int((Gn - 1e-6) / w1))  # facets out from the crease
        names = (("GFL", "GFR", "GFL", "GFR") if nf == 1 else
                 (f"GFL{nf}", "GFR1", f"GFL{nf - j}", f"GFR{1 + j}"))
        if any(n not in P or P[n] is None for n in names):
            return
        nl, nr, wl, wr = (P[n] for n in names)
        self._muzzle(m, piece, nl, nr, (uc, hgt), (0.0, 1.0),
                     (wl, (uc - Gn, hgt)), (wr, (uc + Gn, hgt)))

    def _muzzle(self, m, piece, near_l, near_r, O2, up2, end_l, end_r, polys=None,
                dart_deg=None, names=("Nose", "muzzle"), join=0.0):
        """Birmingham takes a bite out of the end of the loop's centre fold
        and sticks its edges together, which pulls the card either side of
        it back into a curve: a nose. Stiff paper can't curve, so here the
        bite is a dart between two flat facets, one each side of the front
        crease, each creased off the wall's top edge (across the curve of a
        round wall, from the crease to Muzzle Width along it) and meeting
        the other along the dart's seam. The seam leans back over the loop:
        hardly at all when the card is shut, further as the walls open, and
        flat back when they open as far as the dart allows (wider than
        that, real card curves and this can't follow: Checks says so)."""
        # near_l, near_r: the walls each side of the front crease; O2: the
        # crease's top in the pattern, up2: its line on upward; end_l,
        # end_r: (wall, pattern point) where each facet's crease ends
        # polys: each facet's own outline ({-1: left, 1: right}), else a
        # muzzle's; join: a glue tab that wide on the right facet's seam,
        # stuck under the left's (the book's tab across the bite)
        lab = m["label"]
        Ln = float(m.get("face_len", 22.0)) if polys is None else 0.0
        dd = float(m.get("face_dart", 15.0)) if dart_deg is None else dart_deg
        dart = math.radians(max(0.0, min(60.0, dd)))
        tag, word = names
        O = Vector((O2[0], O2[1], 0.0))
        up = Vector((up2[0], up2[1], 0.0)).normalized()
        near = {-1.0: near_l, 1.0: near_r}
        ends = {-1.0: end_l, 1.0: end_r}
        # each facet's own shape: its crease, and its seam edge the dart
        # short of the front crease's line
        shape = {}
        for sx in (-1.0, 1.0):
            h2 = Vector((ends[sx][1][0], ends[sx][1][1], 0.0)) - O
            Gn = h2.length
            h2 = h2 / Gn
            th = h2.angle(up)
            across = (h2 - h2.dot(up) * up).normalized()
            s2 = math.cos(dart) * up + math.sin(dart) * across
            shape[sx] = (h2, s2, Gn, max(0.0, th - dart))
        alpha = 0.5 * (shape[-1.0][3] + shape[1.0][3])
        tight = []

        def seam(t):
            A = near_r.asm(t)
            Pc = A @ O
            c = (A.to_3x3() @ up).normalized()
            gl = (ends[-1.0][0].asm(t) @ Vector((*ends[-1.0][1], 0.0)) - Pc).normalized()
            gr = (ends[1.0][0].asm(t) @ Vector((*ends[1.0][1], 0.0)) - Pc).normalized()
            mm = gl + gr
            rho = 0.5 * mm.length
            if rho < 1e-6:  # (a flat front: one flap, standing straight up)
                return Pc, gl, gr, c
            ca = math.cos(alpha) / rho
            if ca > 1.0 + 1e-9:
                tight.append(t)
            ca = min(1.0, ca)
            mh = mm.normalized()
            kh = c - c.dot(mh) * mh
            kh = kh.normalized() if kh.length > 1e-9 else c
            return Pc, gl, gr, (ca * mh + math.sqrt(1.0 - ca * ca) * kh).normalized()

        for sx in (-1.0, 1.0):
            h2, s2, Gn, _ = shape[sx]
            F2i = frame(O, h2, s2).inverted()

            def asm(t, sx=sx, F2i=F2i):
                Pc, gl, gr, s = seam(t)
                return frame(Pc, gl if sx < 0 else gr, s) @ F2i

            if polys is not None:
                poly = polys[sx]
            else:
                poly = [(O + a_ * h2 + b_ * s2).to_2d()[:]
                        for a_, b_ in ((0.0, 0.0), (Gn, 0.0), (0.45 * Gn, 0.75 * Ln),
                                       (0.0, Ln))]
            side = "L" if sx < 0 else "R"
            p = self.add(Panel(f"{piece}.{tag}{side}", piece, "panel", [poly], asm,
                               near[sx].name, None,
                               f"{lab}: {word} {'left' if sx < 0 else 'right'}"))
            p.free = True  # (creased off a curve: posed opening by opening)
            self.fold_kind[frozenset((near[sx].name, p.name))] = "valley"
        self.fold_kind[frozenset((f"{piece}.{tag}L", f"{piece}.{tag}R"))] = "mountain"
        if join > 0 and f"{piece}.{tag}L" in self.panels and f"{piece}.{tag}R" in self.panels:
            self._bite_tab(piece, f"{piece}.{tag}L", f"{piece}.{tag}R", O, shape, join,
                           f"{lab}: {word} tab")
        for t in self.samples:
            seam(t)
        if tight:
            self.warn(f"{lab}: the {word}'s dart is too wide for how far it opens (from "
                      f"{min(tight):.0f} degrees); narrow its angle, or let the card curve "
                      f"there")

    def _bite_tab(self, piece, nl, nr, O, shape, wd, label):
        """A glue tab on the right facet's seam edge, folded under the left
        facet and stuck there: it holds the bite closed."""
        from .base import TAB_LIFT
        sL, sR = shape[-1.0][1], shape[1.0][1]
        pL = self.panels[nl]
        on = [(Vector((q[0], q[1], 0.0)) - O) for q in self.panels[nr].polys[0]]
        L = max((v.dot(sR) for v in on if abs(v.cross(sR).z) < 1e-4), default=0.0)
        if L < 4.0:
            return
        outR = Vector((-sR.y, sR.x, 0.0))  # (left of the right facet's seam: off it)
        inL = Vector((-sL.y, sL.x, 0.0))  # (left of the left facet's seam: onto it)
        a0, a1 = 0.15 * L, 0.85 * L
        poly = [(O + a0 * sR).to_2d()[:], (O + a1 * sR).to_2d()[:],
                (O + (a1 - 0.3 * wd) * sR + wd * outR).to_2d()[:],
                (O + (a0 + 0.3 * wd) * sR + wd * outR).to_2d()[:]]
        # right facet's seam frame -> left facet's, then a hair behind it
        Mv = frame(O, sL, inL) @ frame(O, sR, outR).inverted()
        Mv = Matrix.Translation((0.0, 0.0, -TAB_LIFT)) @ Mv

        def asm(t, pa=pL.asm, Mv=Mv):
            return pa(t) @ Mv

        self.add(Panel(f"{nr}Tab", piece, "tab", [poly], asm, nl, None, label))

    @staticmethod
    def ear(e0, e1, out, size):
        """An ear: a base tab's outline grown to a point, size out from the
        wall's foot (e0 to e1; out: away from the wall, in the pattern)."""
        e0, e1, out = Vector(e0).to_2d(), Vector(e1).to_2d(), Vector(out).to_2d().normalized()
        ev = (e1 - e0).normalized()
        mid = 0.5 * (e0 + e1)
        return [tuple(e0), tuple(e1), tuple(e1 + 0.5 * size * out + 0.2 * size * ev),
                tuple(mid + size * out), tuple(e0 + 0.5 * size * out - 0.2 * size * ev)]
