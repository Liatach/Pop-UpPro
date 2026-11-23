"""A piece jutting out through a slot (Birmingham 59-60): glued down on a
page by a sticking strip parallel to the spine, it passes through a slot cut
in a face of another mechanism, and the slot rides along it as the card
opens and closes.

model.py has the module's overview and the Model class."""
from mathutils import Matrix, Vector

from .base import Panel, Piece, TAB_LIFT
from .geom import frame


class Slots:
    """Slotted-piece builder. Mixed into Model (model.py)."""

    def _slotted(self, m):
        """The piece hinges on its sticking strip, a line on the page along
        the spine; the slot, cut in the face square to the fold (parallel to
        its creases), is a line along the spine too. Both lines run the same
        way at every opening, so the piece's plane is the one through both:
        it turns about its strip as the face moves, sliding through the
        slot. Its length is how far the slot is from the strip when the card
        is open plus how far it juts out past the face; the strip's distance
        from the spine sets the angle it juts at."""
        from .openings import face_frame
        uid, lab = m["uid"], m["label"]
        face = m.get("face") or ""
        if (face not in self.panels or self.panels[face].kind == "page") and m.get("host"):
            # (not picked yet: the front of what it goes through, or its first face)
            from .align import uid_of
            own = [n for n in self.order if uid_of(n) == m["host"] and
                   self.panels[n].kind == "panel" and self.panels[n].polys]
            face = next((n for n in own if self.panels[n].label.lower().endswith("front")),
                        own[0] if own else face)
        if face not in self.panels:
            self.warn(f"{lab}: pick the face its slot cuts through; skipped")
            return
        fp = self.panels[face]
        if fp.kind == "page":
            self.warn(f"{lab}: its slot cuts through a face of a mechanism, not a page; skipped")
            return
        fr = face_frame(self, face)
        if fr is None:
            self.warn(f"{lab}: its face has no paper; skipped")
            return
        origin, across, up, _ = fr
        page = self.panels["Page.L" if m.get("slot_page", "L") == "L" else "Page.R"]
        sgp = -1.0 if page.name == "Page.L" else 1.0  # (the page's pattern runs out this way)
        w = max(3.0, float(m.get("img_w", 20.0)))
        jut = max(2.0, float(m.get("slot_jut", 30.0)))
        strip = max(1.0, float(m.get("slot_strip", 20.0)))
        tab = max(4.0, min(float(m.get("tab", 8.0)), 15.0))
        x0, y0 = float(m.get("x", 0.0)), float(m.get("y", 20.0))
        c_pat = Vector((origin[0] + x0 * across[0] + y0 * up[0],
                        origin[1] + x0 * across[1] + y0 * up[1], 0.0))
        tm = self.tmax
        # the slot's way: the line the face turns about, seen from the page
        # (the crease it's hinged on, or the spine's way for a box fold's
        # faces): kept along that line, the slot runs the same way as a
        # strip on the page at every opening (or the face doesn't suit)
        P0 = page.asm(tm)

        def rel(t):
            return (page.asm(t).inverted() @ fp.asm(t)).to_3x3()

        R0 = rel(tm)
        ax = None
        for t in self.samples:
            q = (rel(t) @ R0.transposed()).to_quaternion()
            if q.angle < 1e-3:
                continue
            a_ = q.axis.normalized()
            if ax is None:
                ax = a_
            elif ax.cross(a_).length > 0.01:
                ax = False
                break
        fname = fp.label.split(": ", 1)[-1]
        if ax is False or (ax is not None and abs(ax.z) > 0.05):
            self.warn(f"{lab}: {fname} doesn't turn about a line on the "
                      f"{'left' if sgp < 0 else 'right'} page, so a slot in it can't ride "
                      f"along a piece glued there (try the other page); skipped")
            return
        a_page = Vector((0.0, 1.0, 0.0)) if ax is None else Vector((ax.x, ax.y, 0.0)).normalized()
        if a_page.y < 0:
            a_page = -a_page
        d3 = R0.inverted() @ a_page
        dY = Vector((d3.x, d3.y, 0.0))
        if dY.length < 0.95:
            self.warn(f"{lab}: {fname} doesn't turn about a line in it; skipped")
            return
        dY.normalize()
        dN = Vector((-dY.y, dY.x, 0.0))
        half, sw = 0.5 * w + 1.0, 1.0  # (the slot: the piece's width and a little, 2 mm wide)
        self.slots.setdefault(fp.piece, []).append(
            [(c_pat + a * dY + b * dN).to_2d()[:] for a, b in
             ((-half, -sw), (half, -sw), (half, sw), (-half, sw))])
        # the strip: on the page along the slot's way, Strip From Spine out
        # from the spine, level with the slot (square across its way)
        s0 = fp.asm(tm) @ c_pat
        yc = (P0.inverted() @ s0).y
        hp = Vector((sgp * strip, yc, 0.0))
        sp_ = P0.inverted() @ s0
        hp += (Vector((sp_.x, sp_.y, 0.0)) - hp).dot(a_page) * a_page  # (level with it)

        # (aimed a paper's breadth out the face's far side from the strip as
        # it opens out, so open flat, face and piece both lying on the page,
        # it still comes out on top of the face through the slot rather than
        # under it)
        tq = max(5.0, tm - 15.0)
        Fq = fp.asm(tq)
        nq = (Fq.to_3x3() @ Vector((0.0, 0.0, 1.0))).normalized()
        out_ = -1.0 if (page.asm(tq) @ hp - Fq @ c_pat).dot(nq) > 0 else 1.0

        def ends(t):
            """The strip's point and the way from it square to the slot's
            line, opening t, and the slot's way."""
            Pt = page.asm(t)
            h = Pt @ hp
            Yt = (Pt.to_3x3() @ a_page).normalized()
            lift = 1.0 * min(1.0, max(0.0, (float(t) - 90.0) / 60.0))
            s = fp.asm(t) @ (c_pat + Vector((0.0, 0.0, lift * out_)))
            d = s - h
            d -= d.dot(Yt) * Yt
            return h, d, Yt

        reach = {t: ends(t)[1].length for t in self.samples + [tm]}
        L = reach[tm] + jut
        if max(reach.values()) > L - 3.0:
            far = max(reach, key=reach.get)
            L = reach[far] + 3.0
            self.warn(f"{lab}: lengthened to {L:.0f} mm: at {far:.0f} degrees the slot is "
                      f"{reach[far]:.0f} mm from its strip, and the piece must still reach "
                      f"through it")
        if min(reach.values()) < 2.0:
            self.warn(f"{lab}: the slot comes right down onto its strip as the card closes; "
                      f"move the strip further from the spine or the slot higher")
        piece = f"Slot{uid}"
        self.add_piece(Piece(piece, lab, 1 + uid, (0.5 * L, 0.0)))

        def asm_p(t):
            h, d, Yt = ends(t)
            if d.length < 1e-6:
                d = page.asm(t).to_3x3() @ Vector((-sgp, 0.0, 0.0))
            return frame(h, d, Yt)

        body = self.add(Panel(f"{piece}.Piece", piece, "panel",
                              [[(0.0, -0.5 * w), (L, -0.5 * w), (L, 0.5 * w), (0.0, 0.5 * w)]],
                              asm_p, page.name, None, f"{lab}: piece"))
        body.free = True  # (held by its strip and the slot: posed opening by opening)
        # its sticking strip, folded under onto the page, pointing away from
        # where the piece leans
        # (its sticking strip folds under onto the page towards the spine,
        # or away from it when it would reach across)
        tdir = Vector((-a_page.y, a_page.x, 0.0))
        if tdir.x * sgp > 0:
            tdir = -tdir
        if abs(hp.x) < tab + 1.0:
            tdir = -tdir
        xv = -tdir  # (the strip's pattern runs back from the piece, x < 0)
        Mt = Matrix(((xv.x, a_page.x, 0.0, hp.x), (xv.y, a_page.y, 0.0, hp.y),
                     (0.0, 0.0, 1.0, TAB_LIFT), (0.0, 0.0, 0.0, 1.0)))
        if Mt.to_3x3().determinant() < 0:
            Mt = Matrix(((xv.x, a_page.x, 0.0, hp.x), (xv.y, a_page.y, 0.0, hp.y),
                         (0.0, 0.0, -1.0, TAB_LIFT), (0.0, 0.0, 0.0, 1.0)))

        def asm_t(t, pa=page.asm, Mt=Mt):
            return pa(t) @ Mt

        tn = f"{piece}.Strip"
        self.add(Panel(tn, piece, "tab", [[(-tab, -0.5 * w), (0.0, -0.5 * w), (0.0, 0.5 * w),
                                           (-tab, 0.5 * w)]], asm_t, page.name, None,
                       f"{lab}: sticking strip"))
        self.fold_kind[frozenset((body.name, tn))] = "valley"
        host_lab = fp.label.split(":")[0]
        self.stack_ok.add(frozenset((lab, host_lab)))
