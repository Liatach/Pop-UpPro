"""Flapping arms (Birmingham 65-66): a back piece suspended behind a V-fold's
centre crease (or a box fold's front corner), its ends glued to arms that
come out through slots in the halves.

model.py has the module's overview and the Model class."""
import math

from mathutils import Matrix, Vector

from .base import Panel, Piece, TAB_LIFT
from .geom import frame


class Arms:
    """Flapping-arms builder. Mixed into Model (model.py)."""

    def _arms_host(self, m):
        """The two faces either side of the host's crease, as (panel, the
        crease's start in its pattern, the crease's direction, the way
        across the face from the crease), left then right; or None."""
        h = next((x for x in self.mechs if x["uid"] == m.get("host")), None)
        if h is None:
            return None
        if h["type"] == "VFOLD":
            base = f"VFold{h['uid']}"
            out = []
            for side in ("L", "R"):
                p = self.panels.get(f"{base}.Half{side}")
                if p is None:
                    return None
                xs = [q[0] for poly in p.polys for q in poly]
                sx = 1.0 if sum(xs) > 0 else -1.0
                out.append((p, (0.0, 0.0), (0.0, 1.0), (sx, 0.0)))
            return out
        if h["type"] == "BOX":
            base = f"Box{h['uid']}"
            ac, cb = self.panels.get(f"{base}.AC"), self.panels.get(f"{base}.CB")
            if ac is None or cb is None:
                return None
            # the front-top fold C is the edge they share, along the pattern's y
            xa = [q[0] for poly in ac.polys for q in poly]
            xb = [q[0] for poly in cb.polys for q in poly]
            xc = max(xa) if max(xa) <= min(xb) + 1e-6 else min(xa)
            return [(ac, (xc, 0.0), (0.0, 1.0), (-1.0 if sum(xa) / len(xa) < xc else 1.0, 0.0)),
                    (cb, (xc, 0.0), (0.0, 1.0), (1.0 if sum(xb) / len(xb) > xc else -1.0, 0.0))]
        return None

    @staticmethod
    def _arms_open(sides, t):
        """The angle between the two faces, across the crease."""
        u = [(p.asm(t).to_3x3() @ Vector((*sv, 0.0))).normalized() for p, P0, cd, sv in sides]
        return u[0].angle(u[1])

    def _arms(self, m):
        """The back piece and its two halves (G, H) hang behind the crease
        in a four-sided loop with the faces' strips between the crease and
        the slots (E, F): every fold in it runs along the crease, so it
        stays one shape in section, changing as the faces open. Each arm is
        glued to an end of the back piece through its slot, so it turns with
        that half of the back piece, jutting out of the face's front. The
        book's rules: the slots the same distance E from the crease, the
        back piece's halves G = H; the back piece must reach across the gap
        between the slots however far the faces open (G at least E times
        the sine of half their angle)."""
        uid, lab = m["uid"], m["label"]
        sides = self._arms_host(m)
        if sides is None:
            self.warn(f"{lab}: goes on a V-fold or a box fold; pick one in Stands On; skipped")
            return
        E = float(m.get("arm_slot", 15.0) or 15.0)
        G = float(m.get("arm_back", 20.0) or 20.0)
        A = float(m.get("arm_width", 12.0) or 12.0)  # the slot's length along the crease
        La = float(m.get("arm_len", 30.0) or 30.0)
        ys = float(m.get("arm_y", 20.0) or 0.0)  # the slots' lower ends, up the crease
        Wa = max(A + 2.0, float(m.get("arm_hand", 0.0) or 0.0) or A + 6.0)
        mg = 3.0  # how far the back piece's ends reach past the slots (D > A)
        Hb = A + 2.0 * mg
        Cg = min(0.6 * G, 10.0)  # each arm's glue end, behind the slot
        sw = 0.6  # half a slot's width
        neck = 3.0
        if G < E * 0.2:
            self.warn(f"{lab}: the back piece is very short for slots that far out")
        # the slots, cut in the faces
        for p, P0, cd, sv in sides:
            c, s = Vector((*cd, 0.0)), Vector((*sv, 0.0))
            O = Vector((*P0, 0.0))
            pts = [O + (E + a) * s + b * c for a, b in ((-sw, ys), (sw, ys), (sw, ys + A),
                                                       (-sw, ys + A))]
            self.slots.setdefault(p.piece, []).append([v.to_2d()[:] for v in pts])

        def section(t):
            """Where things are, opening t: the crease point O at the
            slots' foot, its direction c, the slots S1, S2, the back
            crease K and each back half's direction out to its slot."""
            out = []
            for p, P0, cd, sv in sides:
                M_ = p.asm(t)
                O = M_ @ Vector((P0[0], P0[1] + ys, 0.0))
                c = (M_.to_3x3() @ Vector((*cd, 0.0))).normalized()
                u = (M_.to_3x3() @ Vector((*sv, 0.0))).normalized()
                out.append((O, c, u))
            (O, c, u1), (_, _, u2) = out
            S1, S2 = O + E * u1, O + E * u2
            b = u1 + u2
            if b.length < 1e-9:  # (opened out flat: behind is off the faces' backs)
                b = u1.cross(c) if u1.cross(c).dot(u2.cross(c)) >= 0 else -u1.cross(c)
            b.normalize()
            half = 0.5 * (S1 - S2).length
            if half > G:
                bad.append(t)
            hh = math.sqrt(max(0.0, G * G - half * half))
            K = 0.5 * (S1 + S2) + hh * b
            d1 = (S1 - K).normalized() if (S1 - K).length > 1e-9 else u1
            d2 = (S2 - K).normalized() if (S2 - K).length > 1e-9 else u2
            return O, c, S1, S2, K, d1, d2

        bad = []
        piece = f"Arms{uid}"
        self.add_piece(Piece(piece, f"{lab} back piece", 1 + uid, (0.0, 0.5 * Hb)))
        y0 = -mg  # (the back piece's bottom, from the slots' foot)

        def asm_bl(t):
            O, c, S1, S2, K, d1, d2 = section(t)
            return frame(K + y0 * c, -d1, c) @ Matrix.Translation((0.0, -y0, 0.0))

        def asm_br(t):
            O, c, S1, S2, K, d1, d2 = section(t)
            return frame(K + y0 * c, d2, c) @ Matrix.Translation((0.0, -y0, 0.0))

        host_l, host_r = sides[0][0], sides[1][0]
        bl = self.add(Panel(f"{piece}.BackL", piece, "panel",
                            [[(-G, y0), (0.0, y0), (0.0, y0 + Hb), (-G, y0 + Hb)]], asm_bl,
                            host_l.name, None, f"{lab}: back piece left (G)"))
        br = self.add(Panel(f"{piece}.BackR", piece, "panel",
                            [[(0.0, y0), (G, y0), (G, y0 + Hb), (0.0, y0 + Hb)]], asm_br,
                            host_r.name, None, f"{lab}: back piece right (H)"))
        for p in (bl, br):
            p.free = True  # (held by the arms in the slots: posed opening by opening)
        self.fold_kind[frozenset((bl.name, br.name))] = "valley"
        # the arms
        for side, back, sg in (("L", bl, -1.0), ("R", br, 1.0)):
            ap = f"Arm{side}{uid}"
            self.add_piece(Piece(ap, f"{lab} {'left' if side == 'L' else 'right'} arm",
                                 1 + uid, (0.5 * La, 0.5 * A)))
            mid = 0.5 * A
            poly = [(0.0, mid - 0.5 * (A - 1.0)), (neck, mid - 0.5 * (A - 1.0)),
                    (neck, mid - 0.5 * Wa), (La, mid - 0.5 * Wa), (La, mid + 0.5 * Wa),
                    (neck, mid + 0.5 * Wa), (neck, mid + 0.5 * (A - 1.0)),
                    (0.0, mid + 0.5 * (A - 1.0))]

            def asm_a(t, side=side):
                O, c, S1, S2, K, d1, d2 = section(t)
                S, d = (S1, d1) if side == "L" else (S2, d2)
                return frame(S, d, c)

            arm = self.add(Panel(f"{ap}.Arm", ap, "panel", [poly], asm_a, back.name, None,
                                 f"{lab}: {'left' if side == 'L' else 'right'} arm"))
            arm.free = True
            # its glue end, behind the slot, wider than it, stuck to the back
            # piece's end on its back
            gpoly = [(-Cg, -mg + 0.5), (0.0, -mg + 0.5), (0.0, A + mg - 0.5),
                     (-Cg, A + mg - 0.5)]
            # arm pattern -> back piece pattern: x back from the slot to the
            # back piece's end, y the same (the back piece's y from the slots' foot)
            Mv = (Matrix.Translation((sg * G, 0.0, 0.0)) @
                  Matrix(((sg, 0.0, 0.0, 0.0), (0.0, 1.0, 0.0, 0.0),
                          (0.0, 0.0, sg, 0.0), (0.0, 0.0, 0.0, 1.0))))
            Mv = Matrix.Translation((0.0, 0.0, -TAB_LIFT)) @ Mv

            def asm_g(t, pa=back.asm, Mv=Mv):
                return pa(t) @ Mv

            self.add(Panel(f"{ap}.Glue", ap, "tab", [gpoly], asm_g, back.name, None,
                           f"{lab}: {'left' if side == 'L' else 'right'} arm's glue end"))
        self.stack_ok.add(frozenset((lab, f"{lab} back piece")))
        for t in self.samples:
            section(t)
        # a face that opens out flat (a box fold's corner on the open card)
        # leaves the back piece standing behind it unless G is just E
        flat = max(self.samples + [self.tmax], key=lambda t: self._arms_open(sides, t))
        if self._arms_open(sides, flat) > math.radians(175.0) and G > E + 0.5:
            self.warn(f"{lab}: its faces open out flat, so the back piece must be as long as "
                      f"the slots are far from the crease ({E:.0f} mm) to fold flat with "
                      f"them")
        if bad:
            self.warn(f"{lab}: the back piece can't reach across between the slots past "
                      f"{min(bad):.0f} degrees; make it longer, or the slots nearer the crease")
