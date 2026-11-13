"""An animal face on a loop or tube (Birmingham 17, after the curves of 15
and 16): the top edge carries on up past the front crease as a muzzle, folded
back over the loop by a dart.

model.py has the module's overview and the Model class."""
import math

from mathutils import Vector

from .base import Panel
from .geom import frame


class Faces:
    """Animal-face builder. Mixed into Model (model.py)."""

    def _tube_face(self, m, piece, P, uc, hgt, nf, wf):
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
        lab = m["label"]
        Gn = min(float(m.get("face_width", 18.0)), wf)
        Ln = float(m.get("face_len", 22.0))
        dart = math.radians(max(0.0, min(60.0, float(m.get("face_dart", 15.0)))))
        w1 = wf / nf  # a facet's width

        def wall(sx):
            j = min(nf - 1, int((Gn - 1e-6) / w1))  # facets out from the crease
            if nf == 1:
                return "GFL" if sx < 0 else "GFR"
            return f"GFL{nf - j}" if sx < 0 else f"GFR{1 + j}"

        near = {-1.0: "GFL" if nf == 1 else f"GFL{nf}", 1.0: "GFR" if nf == 1 else "GFR1"}
        if any(n not in P or P[n] is None for n in (wall(-1.0), wall(1.0), near[-1.0],
                                                    near[1.0])):
            return
        tight = []

        def seam(t):
            A = P[near[1.0]].asm(t)
            Pc = A @ Vector((uc, hgt, 0.0))
            c = (A.to_3x3() @ Vector((0.0, 1.0, 0.0))).normalized()
            gl = (P[wall(-1.0)].asm(t) @ Vector((uc - Gn, hgt, 0.0)) - Pc).normalized()
            gr = (P[wall(1.0)].asm(t) @ Vector((uc + Gn, hgt, 0.0)) - Pc).normalized()
            mm = gl + gr
            rho = 0.5 * mm.length
            if rho < 1e-6:  # (a flat front: one flap, standing straight up)
                return Pc, gl, gr, c
            ca = math.sin(dart) / rho  # cos of (90 degrees - dart), the facet's angle
            if ca > 1.0 + 1e-9:
                tight.append(t)
            ca = min(1.0, ca)
            mh = mm.normalized()
            kh = c - c.dot(mh) * mh
            kh = kh.normalized() if kh.length > 1e-9 else c
            return Pc, gl, gr, (ca * mh + math.sqrt(1.0 - ca * ca) * kh).normalized()

        for sx in (-1.0, 1.0):
            h2 = Vector((sx, 0.0, 0.0))
            s2 = Vector((sx * math.sin(dart), math.cos(dart), 0.0))
            O = Vector((uc, hgt, 0.0))
            F2i = frame(O, h2, s2).inverted()

            def asm(t, sx=sx, F2i=F2i):
                Pc, gl, gr, s = seam(t)
                return frame(Pc, gl if sx < 0 else gr, s) @ F2i

            poly = [(O + a_ * h2 + b_ * s2).to_2d()[:]
                    for a_, b_ in ((0.0, 0.0), (Gn, 0.0), (0.45 * Gn, 0.75 * Ln), (0.0, Ln))]
            side = "L" if sx < 0 else "R"
            p = self.add(Panel(f"{piece}.Nose{side}", piece, "panel", [poly], asm,
                               P[near[sx]].name, None,
                               f"{lab}: muzzle {'left' if sx < 0 else 'right'}"))
            p.free = True  # (creased off a curve: posed opening by opening)
            self.fold_kind[frozenset((P[near[sx]].name, p.name))] = "valley"
        self.fold_kind[frozenset((f"{piece}.NoseL", f"{piece}.NoseR"))] = "mountain"
        for t in self.samples:
            seam(t)
        if tight:
            self.warn(f"{lab}: the nose's dart is too wide for how far the front opens "
                      f"(from {min(tight):.0f} degrees); narrow Nose Dart or Muzzle Width, "
                      f"or let the card curve there")
