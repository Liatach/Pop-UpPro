"""Stage sets and carousels (Birmingham 118): frames, floors and ceilings,
the folds where they meet the walls, and a stage's peaked roof."""
import math

from mathutils import Vector

from .base import Host, Panel, Piece, T_MIN
from .geom import Z, clip_halfplane, frame


class Stages:
    """Stage set builders. Mixed into Model (model.py)."""

    # ----------------------------------------------------------- stage set
    def _frame(self, m, host):
        """Stage frame (Birmingham 118): a panel across the stage, glued by a
        tab down each side to the pages at Depth from the spine, with a
        centre crease that folds back towards the spine as the stage closes.
        Each half is Depth x sin(open/2) wide, so the frame pulls flat
        exactly when the stage is fully open (360/n degrees in a carousel):
        it is the frames, floors and ceilings that stop the stage there."""
        uid, lab = m["uid"], m["label"]
        if not host.is_spine and host.open_max is None:
            self.warn(f"{lab}: frames stand in a stage (a carousel stage or a stage set)")
            return
        om = host.open_max or self.tmax
        Wd, Hd = host.size or (self.W, self.H)
        a = min(float(m["x"]), Wd)
        y0 = max(0.0, float(m.get("y", 0.0)))
        y1 = min(Hd, y0 + float(m.get("height", Hd)))
        B = a * math.sin(math.radians(0.5 * om))
        if a < 5.0 or y1 - y0 < 5.0 or B < 3.0:
            self.warn(f"{lab}: too small; skipped")
            return
        piece = f"Frame{uid}"
        self.add_piece(Piece(piece, lab, 1 + uid, (0.0, 0.5 * (y0 + y1)))).upright = True

        def dirs(t):
            S, e, xh, Y, sn, cs = self.strip_frame(host, t)
            s = math.sqrt(max(B * B - a * a * sn * sn, 0.0))
            fL = S + a * cs * e - a * sn * xh
            dL = (a * sn * xh - s * e) / B  # crease dips towards the spine
            dR = (a * sn * xh + s * e) / B
            return fL + B * dL, dL, dR, Y

        def asm_L(t):
            C0, dL, dR, Y = dirs(t)
            return frame(C0, dL, Y)

        def asm_R(t):
            C0, dL, dR, Y = dirs(t)
            return frame(C0, dR, Y)

        # Floors rise into the stage and ceilings drop into it as it closes:
        # cut the frame's bottom (top) back so it clears them all the way.
        polyL = [(-B, y0), (0, y0), (0, y1), (-B, y1)]
        for fl, fkey in self.floors:
            if fkey != host.key:
                continue
            half = self.panels.get(f"VFold{fl}.HalfL")
            if half is None:
                continue
            for t in self.samples:
                if t > self.tmax - 0.5:
                    continue
                F, M = half.asm(t), asm_L(t)
                nF = F.to_3x3() @ Z
                n2 = (nF.dot(M.col[0].to_3d()), nF.dot(M.col[1].to_3d()))
                if math.hypot(*n2) < 0.2:
                    continue  # lying flat together: stacked, not crossing
                d0 = nF.dot(M.translation - F.translation)
                mid = (-0.5 * B, 0.5 * (y0 + y1))
                if n2[0] * mid[0] + n2[1] * mid[1] + d0 < 0:
                    n2, d0 = (-n2[0], -n2[1]), -d0
                polyL = clip_halfplane(polyL, n2, 1.0 - d0)
                if len(polyL) < 3:
                    self.warn(f"{lab}: squeezed out by the floor or ceiling; skipped")
                    return
        polyR = [(-x, y) for x, y in polyL]
        HL = self.add(Panel(f"{piece}.L", piece, "panel", [polyL], asm_L, host.p1, None,
                            f"{lab}: left half"))
        HL.hinge = self._hinge_on(host.p1, asm_L, (-B, y1), (-B, y0))
        HR = self.add(Panel(f"{piece}.R", piece, "panel", [polyR], asm_R, host.p2, None,
                            f"{lab}: right half"))
        HR.hinge = self._hinge_on(host.p2, asm_R, (B, y0), (B, y1))
        # closed form: the half's angle to its page
        h_ = "radians(T)/2"
        q_ = f"sqrt(max({B * B:.9g}-{a * a:.9g}*sin({h_})*sin({h_}),0))"
        ex = f"atan2(-{q_},{a:.9g}*sin({h_}))-{h_}"

        def fn(t):
            hh = math.radians(max(t, T_MIN)) / 2
            q = math.sqrt(max(B * B - a * a * math.sin(hh) ** 2, 0.0))
            return math.atan2(-q, a * math.sin(hh)) - hh

        if host.is_spine:  # opening = the card's: closed form; on a stage set, tabulated
            for hh in (HL, HR):
                hh.hinge.kind = "EXPR"
                hh.hinge.sph = dict(var="t", fn=fn, expr=ex)
        # side tabs fold back behind the frame and glue to the pages, clear of
        # the floor's and ceiling's tabs along the page edges
        w = min(float(m.get("tab", 8.0)), 0.5 * a)
        ys = [q[1] for q in polyL if abs(q[0] + B) < 1e-6] or [y0, y1]
        ya, yb = min(ys), max(ys)
        et = self.edge_tab.get(host.key, {})
        if "bottom" in et:
            ya = max(ya, et["bottom"] + 1.0)
        if "top" in et:
            yb = min(yb, Hd - et["top"] - 1.0)
        c = min(0.3 * w, 0.2 * (yb - ya))
        for side, half, x, sgn, pg in (("L", HL, -B, -1.0, host.p1), ("R", HR, B, 1.0, host.p2)):
            if yb - ya < 4.0:
                break
            poly = [(x, ya), (x, yb), (x + sgn * w, yb - c), (x + sgn * w, ya + c)]
            tasm = self._glue_asm(self.panels[pg], half.asm, (x, ya), (x, yb),
                                  (sgn, 0.0), (-sgn, 0.0))
            self.add(Panel(f"{piece}.Tab{side}", piece, "tab", [poly], tasm, pg, None,
                           f"{lab}: side tab {side}"))
        self.frames[uid] = dict(depth=a, width=2 * B, label=lab, host=host.key, open=om)

    def _floor(self, m, host):
        """Floor (or ceiling) of a stage: a V-fold whose glue lines run along
        the bottom (top) edges of the pages, straight out from the fold. Its
        two halves meet the pages at half the stage angle, so it lies flat
        when the stage is fully open and folds up into the stage (down, for a
        ceiling) as it closes."""
        ceiling = m["type"] == "CEILING"
        om = host.open_max or self.tmax
        Wd, Hd = host.size or (self.W, self.H)
        if host.open_max is not None and not ceiling:
            self.warn(f"{m['label']}: a stage set stands on the card, which is its floor; "
                      f"skipped")
            return
        if not host.is_spine and host.open_max is None:
            self.warn(f"{m['label']}: floors and ceilings go in a stage; skipped")
            return
        if om > 150.0:
            # flat at 180 it would have to lie in the page planes a moment
            # later: paper can't do that, so floors need three stages or more
            self.warn(f"{m['label']}: floors and ceilings need a card or stage that opens "
                      f"to under 150 degrees (set Opens To, or a carousel of three or "
                      f"more stages); skipped")
            return
        depth = min(float(m.get("depth", Wd)), Wd)
        al = 0.5 * om
        ca, sa = math.cos(math.radians(al)), math.sin(math.radians(al))
        # Its centre crease can run on past the front of the stage (a pointed
        # apron): shut, the crease lies on the page at half the stage angle
        # to the edge it's glued along, so it may reach Wd / cos and Hd / sin.
        lead = max(0.0, float(m.get("lead", 0.0)))
        Lc = depth * ca + lead
        Lmax = min(Wd / ca, Hd / sa) - 0.5
        if Lc > Lmax + 1e-6:
            self.warn(f"{m['label']}: its point can reach {Lmax - depth * ca:.0f} mm past the "
                      f"front at most before it sticks out when shut; shortened")
            Lc = Lmax
        d = dict(m, type="VFOLD", phi_l=90.0, phi_r=90.0, alpha_l=al, alpha_r=al,
                 glue=depth, height=Lc, shape="TRI",
                 y=Hd if ceiling else 0.0, tab_side="OUT" if ceiling else "IN",
                 pref=(0.0, -1.0) if ceiling else (0.0, 1.0),
                 flip=not ceiling)  # printed side into the stage
        self._vfold(d, host)
        base = f"VFold{m['uid']}"
        # its own crease (the V-fold host made by _vfold) from the stage side
        # is the far side of a mountain fold: V-folds stand there (they fold
        # flat over the crease as the stage shuts), boxes can't
        if f"{base}.HalfL" in self.panels:
            self.floors.append((m["uid"], host.key))
            self.edge_tab.setdefault(host.key, {})["top" if ceiling else "bottom"] = \
                float(m.get("tab", 8.0))
            self._joint_hosts(m, host, base)

    def _joint_hosts(self, m, host, base):
        """Where a floor or ceiling meets each wall is a fold too: hosts for
        box folds, V-folds and the rest standing in that corner (Side picks
        the left or right wall). Position runs out from the stage's fold."""
        for side, page, half in (("L", host.p1, f"{base}.HalfL"),
                                 ("R", host.p2, f"{base}.HalfR")):
            hp = self.panels[half].hinge
            Hp, Fc = hp.Hp, hp.Fc  # the glue line in the wall's and the half's patterns
            # which side of the glue line each lies on (its own X)
            def side_of(panel, F):
                Fi = F.inverted()
                xs = [(Fi @ Vector((q[0], q[1], 0))).x for poly in self.panels[panel].polys
                      for q in poly]
                return 1.0 if sum(xs) > 0 else -1.0
            sw, sh = side_of(page, Hp), side_of(half, Fc)
            if sw == sh:
                continue  # printed faces don't face into the corner
            T1, p1, T2, p2 = (Hp, page, Fc, half) if sw < 0 else (Fc, half, Hp, page)
            h = Host(self, p1, 0.0, 0.0, p2, 0.0, 0.0, f"{m['label']}: {side} wall",
                     T1, T2).finish()
            if h.lift != (1.0, 1.0):
                continue
            h.trig = False
            h.key = (m["uid"], side)
            self.hosts[(m["uid"], side)] = h

    def _cut_above(self, m, host):
        """A V-fold roof or ceiling on the spine: cut the background away
        above its glue lines (each side at its own glue angle)."""
        lab = m["label"]
        if not host.is_spine:
            self.warn(f"{lab}: Cut Away Background Above works on the card's spine; "
                      f"not cut")
            return
        W, H = self.W, self.H
        yP = float(m.get("y", 0.0))
        if not 0.0 < yP < H - 1e-6:
            return
        for sx, key in ((-1.0, "phi_l"), (1.0, "phi_r")):
            phi = float(m.get(key, m.get("phi_l", 60.0)))
            if phi <= 90.5:
                self.warn(f"{lab}: its glue lines rise from the spine, so the cut would "
                          f"take the V-fold's own ground; not cut (set the Glue Angle "
                          f"over 90)")
                return
        for sx, key in ((-1.0, "phi_l"), (1.0, "phi_r")):
            phi = float(m.get(key, m.get("phi_l")))
            sp, cp = math.sin(math.radians(phi)), math.cos(math.radians(phi))
            yE = yP + W * cp / sp
            region = [(0.0, yP), (0.0, H), (sx * W, H), (sx * W, yE)]
            if yE < 0.0:
                xb = -yP * sp / cp
                region = [(0.0, yP), (0.0, H), (sx * W, H), (sx * W, 0.0), (sx * xb, 0.0)]
            self.carve("Card", region, {"Page.L", "Page.R"},
                       f"{lab} cut-away {'left' if sx < 0 else 'right'}")

    def _roof_stage(self, m, host):
        """A peaked roof over a stage (or a card): the background is cut to a
        gable along two eaves lines falling from the spine, and a V-fold is
        glued along them with its crease rising to a ridge. Shut, the roof
        lies flat in the cut-away corners; open, it stands over the stage,
        its ridge level at full opening (a stage) or at 90 degrees (a card)
        with Level Ridge, or at the piece angle given.

        Valley: the same upside down (the card folds the same either way
        up): the background cut away below two lines rising from the spine,
        a V-fold floor glued along them dipping to a valley."""
        lab = m["label"]
        valley = bool(m.get("valley"))
        what = "valley floor" if valley else "roof"
        if not host.is_spine:
            self.warn(f"{lab}: a {what} goes on the card's spine; skipped")
            return
        W, H = self.W, self.H
        y = max(0.0, min(float(m.get("y", 0.85 * H)), H))
        yR = H - y if valley else y  # worked in roof terms: the card upside down
        phi = float(m.get("phi_l", 100.0))
        if phi <= 92.0:
            self.warn(f"{lab}: the slope must run away from the spine past level (over 90 "
                      f"degrees); set to 100")
            phi = 100.0
        phiA = 180.0 - phi if valley else phi  # the V-fold's real glue angle
        sp, cp = math.sin(math.radians(phi)), math.cos(math.radians(phi))
        reach = min(W / sp, yR / max(-cp, 1e-6))  # to the side edge, or the far edge
        g = min(float(m.get("glue", reach)), reach)

        def flip(pts):
            return [(x, H - yy) for x, yy in pts] if valley else pts

        # cut the background away beyond the eaves lines
        yE = yR + W * cp / sp
        for sx in (-1.0, 1.0):
            region = [(0.0, yR), (0.0, H), (sx * W, H), (sx * W, yE)]
            if yE < 0.0:  # the eaves reach the far edge first
                xb = -yR * sp / cp
                region = [(0.0, yR), (0.0, H), (sx * W, H), (sx * W, 0.0), (sx * xb, 0.0)]
            if yR < H - 1e-6:
                self.carve("Card", flip(region), {"Page.L", "Page.R"},
                           f"{lab} {'cut-away' if valley else 'gable'}")
        # level at the stage's full opening; a whole card is level at 90
        # degrees (flat open, a roof can only lie flat)
        tm = self.tmax if self.tmax < 179.0 else 90.0
        sA, cA = math.sin(math.radians(phiA)), math.cos(math.radians(phiA))
        up = -1.0 if valley else 1.0

        def crease_up(al):
            key = f"__roof{m['uid']}"
            self.joints[key] = dict(host=host, y=y, uL=(-sA, cA), uR=(sA, cA),
                                    aL=math.radians(al), aR=math.radians(al),
                                    pref=(0.0, up))
            self._branch.pop(key, None)
            c = self.crease(key, tm)[0]
            Y = host.L(tm).to_3x3() @ Vector((0.0, 1.0, 0.0))
            del self.joints[key]
            self._branch.pop(key, None)
            return up * c.dot(Y)

        al = float(m.get("alpha_l", 70.0))
        if m.get("level", True):
            lo, hi = 5.0, 89.0  # the ridge climbs as the piece angle grows
            if crease_up(lo) > 0 or crease_up(hi) < 0:
                self.warn(f"{lab}: no piece angle levels the ridge at this slope; "
                          f"using {al:.0f}")
            else:
                for _ in range(40):
                    mid = 0.5 * (lo + hi)
                    if crease_up(mid) > 0:
                        hi = mid
                    else:
                        lo = mid
                al = 0.5 * (lo + hi)
        # shut, the crease lies at (slope - piece angle) from the spine: past
        # this length it pokes out of the closed card
        tilt = math.radians(phi - al)
        ct, st_ = abs(math.cos(tilt)), abs(math.sin(tilt))
        fit = min((H - yR) / ct if ct > 1e-6 else 1e9, W / st_ if st_ > 1e-6 else 1e9) - 0.5
        Lc = max(1.0, float(m.get("height", 60.0)))
        if Lc > fit + 1e-6:
            self.warn(f"{lab}: its {'valley' if valley else 'ridge'} sticks out of the closed "
                      f"card by {Lc - fit:.0f} mm (fits up to {fit:.0f} mm; start it further "
                      f"from the {'bottom' if valley else 'top'} edge, or change the slope "
                      f"or the piece angle)")
        d = dict(m, type="VFOLD", phi_l=phiA, phi_r=phiA, alpha_l=al, alpha_r=al, glue=g,
                 height=Lc, shape="TRI", y=y, tab_side=m.get("tab_side", "IN"),
                 pref=(0.0, up), flip=valley, lines=m.get("lines", []))
        n0 = len(self.warnings)
        self._vfold(d, host)
        for i in range(n0, len(self.warnings)):
            w = self.warnings[i]
            if w.startswith(f"{lab}: tears if opened past"):
                deg = w.split("past ")[1].split(" ")[0]
                self.warnings[i] = (f"{lab}: a {'peaked roof' if not valley else 'valley floor'} can't open out flat; it tears "
                                    f"past {deg} degrees (it's made for carousel stages, "
                                    f"which open less)")
        self.roofs = getattr(self, "roofs", {})
        self.roofs[m["uid"]] = dict(alpha=al, ridge=Lc, eaves=g, reach=reach, fit=fit)

    def _stage(self, m, host):
        """Stage set in a card (Birmingham 118 on a V-fold): the background is
        a V-fold whose halves are square to its centre crease, glued along its
        bottom edges at the Glue Angle either side of the fold. It opens to
        twice the glue angle when the card is flat; frames and a ceiling stand
        in it as in a carousel stage, sized to pull flat right then."""
        phi = float(m.get("phi_l", 60.0))
        if not 10.0 <= phi <= 85.0:
            self.warn(f"{m['label']}: glue angle must be between 10 and 85 degrees")
            phi = max(10.0, min(85.0, phi))
        A, Hs = float(m["glue"]), float(m["height"])
        low = Hs * math.sin(math.radians(phi))
        if float(m["y"]) < low - 1e-6:
            self.warn(f"{m['label']}: shut, its back crease lies {low:.0f} mm down the card "
                      f"from where it stands; move it at least that far up")
        d = dict(m, type="VFOLD", phi_l=phi, phi_r=phi, alpha_l=90.0, alpha_r=90.0,
                 shape="QUAD", tab_side=m.get("tab_side", "OUT"), flip=True)
        self._vfold(d, host)
        base = f"VFold{m['uid']}"
        if f"{base}.HalfL" not in self.panels:
            return
        self.pieces[base].upright = True
        # seen from inside the stage the card's right half is on the left
        h = Host(self, f"{base}.HalfR", 0.0, 0.0, f"{base}.HalfL", 0.0, 0.0, m["label"]).finish()
        h.open_max, h.size, h.key = 2.0 * phi, (A, Hs), m["uid"]
        h.trig = False
        self.hosts[(m["uid"], "S")] = h
