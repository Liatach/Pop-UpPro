"""Parallelogram stand-ups and pictures glued on a face."""
import math

from mathutils import Matrix

from .base import Hinge, Host, Panel, Piece, TAB_LIFT
from .geom import frame, hinge_frame_2d


class StandUps:
    """Stand-up and picture builders. Mixed into Model (model.py)."""

    # ---------------------------------------------------------------- picture
    def _picture(self, m):
        """A piece of card glued flat onto one face of anything (a box's top
        or front, a V-fold half, a 45 degree triangle, a page): Width by
        Height from its bottom left corner, which sits X across the face from
        its centre and Y up from its bottom edge; turned about that corner. It may reach past the face's
        edges: on a box's front it stands up as a stand-up does."""
        from .openings import face_frame
        uid, lab = m["uid"], m["label"]
        face = m.get("face") or ""
        if face not in self.panels:
            self.warn(f"{lab}: pick the face it's glued on; skipped")
            return
        fr = face_frame(self, face)
        if fr is None:
            self.warn(f"{lab}: its face has no paper; skipped")
            return
        origin, across, up, _ = fr
        w, h = float(m.get("img_w", 30.0)), float(m.get("img_h", 30.0))
        x0, y0 = float(m.get("x", 0.0)), float(m.get("y", 0.0))
        turn = math.radians(float(m.get("turn", 0.0)))
        back = m.get("pic_side") == "BACK"
        c, s_ = math.cos(turn), math.sin(turn)
        # picture pattern (x across, y up from its bottom centre) -> face pattern
        ax = (c * across[0] + s_ * up[0], c * across[1] + s_ * up[1])
        ay = (-s_ * across[0] + c * up[0], -s_ * across[1] + c * up[1])
        o = (origin[0] + x0 * across[0] + y0 * up[0], origin[1] + x0 * across[1] + y0 * up[1])
        sgn = -1.0 if back else 1.0  # on the back: seen from behind, not mirrored
        M = Matrix(((sgn * ax[0], ay[0], 0.0, o[0]), (sgn * ax[1], ay[1], 0.0, o[1]),
                    (0.0, 0.0, sgn, sgn * 2.0 * TAB_LIFT), (0.0, 0.0, 0.0, 1.0)))
        host = self.panels[face]
        piece = f"Pic{uid}"
        self.add_piece(Piece(piece, lab, 1 + uid, (0.5 * w, 0.5 * h)))
        rect = [[(0.0, 0.0), (w, 0.0), (w, h), (0.0, h)]]
        bl = self.blend.get(face)
        if bl is not None:
            # on paper that bends (the double 45's top piece): it bends with
            # it, a mix of where the face's two stiff ends would put it
            a_, b_, ya, yb = bl[:4]
            pa, pb = self.panels[a_].asm, self.panels[b_].asm
            rows = 12
            ys_ = [h * k / rows for k in range(rows + 1)]
            polys = [[(0.0, ys_[k]), (w, ys_[k]), (w, ys_[k + 1]), (0.0, ys_[k + 1])]
                     for k in range(rows)]
            main = self.add(Panel(f"{piece}.Face", piece, "panel", polys,
                                  (lambda t, pa=pa, M=M: pa(t) @ M), a_, None,
                                  f"{lab}: picture"))
            helper = Panel(f"{piece}.Bend", piece, "panel", [],
                           (lambda t, pb=pb, M=M: pb(t) @ M), b_, None, f"{lab}: bend")
            helper.helper = True
            self.add(helper)
            self.blend[main.name] = (main.name, helper.name, ya, yb, M)
        else:
            pa = host.asm
            self.add(Panel(f"{piece}.Face", piece, "panel", rect,
                           (lambda t, pa=pa, M=M: pa(t) @ M), face, None, f"{lab}: picture"))
        self.stack_ok.add(frozenset((lab, host.label.split(":")[0])))

    # ---------------------------------------------------- parallelogram stand-up
    def _standup(self, m, host):
        """Birmingham 38. A picture held parallel to the background by a small
        bridge (Upright), or parallel to the floor on a small leg (Flat, the
        flying carpet). Seen from the side it is a box fold: background a,
        bridge (or picture) b, picture (or leg) a, floor b; but the picture
        is its own piece, as wide and tall as you like, and the bridge or leg
        is a separate strip glued to its back."""
        uid = m["uid"]
        a, b = float(m["height"]), float(m["depth"])
        y0, w = float(m["y"]), float(m["width"])
        Wi, Hi = float(m.get("img_w", w)), float(m.get("img_h", a))
        t_ = float(m.get("tab", 10.0))
        lab = m["label"]
        flat = m.get("stand") == "FLAT"
        if Wi < w:
            self.warn(f"{lab}: picture narrower than its {'leg' if flat else 'bridge'}; "
                      f"widened to {w:.0f} mm")
            Wi = w
        need = b if flat else a
        if Hi < need:
            self.warn(f"{lab}: picture shorter than the {'leg reach' if flat else 'bridge height'}"
                      f"; lengthened to {need:.0f} mm")
            Hi = need
        if host.is_spine and a + b > self.W + 1e-6:
            self.warn(f"{lab}: height + depth ({a + b:.0f} mm) is deeper than the page, so it "
                      f"sticks out when closed")
        vc = 0.5 * w
        lift1, lift2 = host.lift
        base = f"Stand{uid}"
        AC, CB = f"{base}.AC", f"{base}.CB"
        img = self.add_piece(Piece(base, lab, 1 + uid, (0.5 * Wi - vc, 0.5 * Hi)))
        img.upright = True
        strip = f"Bridge{uid}"
        if m.get("stand") != "TAIL":
            self.add_piece(Piece(strip, f"{lab} {'leg' if flat else 'bridge'}", 700 + uid,
                                 (0.5 * (a + b), vc)))

        def asm_tabA(t):
            S, l, r, Y, nl, nr = host.dirs(t)
            return frame(S + a * l + y0 * Y + lift1 * TAB_LIFT * nl, l, Y)

        def asm_ac(t):
            S, l, r, Y, nl, nr = host.dirs(t)
            return frame(S + a * l + y0 * Y, r, Y)

        def asm_cb(t):
            S, l, r, Y, nl, nr = host.dirs(t)
            return frame(S + (a + b) * l + b * r + y0 * Y, -l, Y)

        def asm_tabB(t):
            S, l, r, Y, nl, nr = host.dirs(t)
            return frame(S + (a + 2 * b) * r + y0 * Y + lift2 * TAB_LIFT * nr, -r, Y)

        under = Matrix.Translation((0.0, 0.0, -TAB_LIFT))
        # the picture runs from its bridge's (or leg's) start, up the fold
        xl, xr = -vc, Wi - vc
        tail = m.get("stand") == "TAIL"
        if tail:
            # one piece: the picture's paper runs on below it along the floor
            # to the corner (glued), up the background (glued), out again as
            # the bridge and down onto the picture's back (a tab): a small box
            # rolled up behind it. Pattern: x along the fold, y up the picture
            M = Matrix(((0, -1, 0, a + b), (1, 0, 0, vc), (0, 0, 1, 0), (0, 0, 0, 1)))
            hb = 0.5 * w
            tc = min(t_, a)
            chc = min(0.3 * tc, 0.25 * w)
            gap = 0.4  # (each glued face stops short of the folds either side)
            self.add(Panel(CB, base, "panel", [[(xl, 0), (xr, 0), (xr, Hi), (xl, Hi)]],
                           lambda t: asm_cb(t) @ M, host.p2,
                           Hinge(host.T2 @ hinge_frame_2d((b, y0 + vc), (0, 1)),
                                 hinge_frame_2d((0, 0), (1, 0))), f"{lab}: picture"))

            def asm_floor(t):
                S, l, r, Y, nl, nr = host.dirs(t)
                return frame(S + b * r + (y0 + vc) * Y + lift2 * TAB_LIFT * nr, Y, r)

            def asm_wall(t):
                S, l, r, Y, nl, nr = host.dirs(t)
                return frame(S - b * l + (y0 + vc) * Y + lift1 * TAB_LIFT * nl, Y, -l)

            def asm_top(t):
                S, l, r, Y, nl, nr = host.dirs(t)
                return frame(S + a * l - (a + b) * r + (y0 + vc) * Y, Y, -r)

            self.add(Panel(f"{base}.Foot", base, "tab",
                           [[(-hb, -b + gap), (hb, -b + gap), (hb, 0), (-hb, 0)]],
                           asm_floor, host.p2, None, f"{lab}: tail on the floor"))
            self.add(Panel(f"{base}.TabA", base, "tab",
                           [[(-hb, -b - a), (hb, -b - a), (hb, -b - gap), (-hb, -b - gap)]],
                           asm_wall, host.p1, None, f"{lab}: tail on the background"))
            self.add(Panel(AC, base, "panel",
                           [[(-hb, -2 * b - a), (hb, -2 * b - a), (hb, -b - a), (-hb, -b - a)]],
                           asm_top, host.p1,
                           Hinge(host.T1 @ hinge_frame_2d((-a, y0), (0, 1)),
                                 hinge_frame_2d((-vc, -b - a), (1, 0))), f"{lab}: bridge"))
            yc = -2 * b - a
            self.add(Panel(f"{base}.TabC", base, "tab",
                           [[(-hb + chc, yc - tc), (hb - chc, yc - tc), (hb, yc), (-hb, yc)]],
                           (lambda t: asm_cb(t) @ M @
                            Matrix.Translation((0.0, 2 * a + 2 * b, -TAB_LIFT))), CB, None,
                           f"{lab}: tail tab on the picture's back"))
            Mi = M.inverted()
            K = Matrix(((0, 1, 0, -vc), (-1, 0, 0, -a - b), (0, 0, 1, 0), (0, 0, 0, 1)))
            TA = K @ Matrix.Translation((0.0, -y0, 0.0))
            TC1 = K @ Matrix.Translation((b, -y0, 0.0))
            TC2 = Mi @ Matrix.Translation((b, -y0, 0.0))
            TB = Mi @ Matrix.Translation((a + b, -y0, 0.0))
        elif not flat:
            # picture pattern: x along the fold, y up from the floor
            M = Matrix(((0, -1, 0, a + b), (1, 0, 0, vc), (0, 0, 1, 0), (0, 0, 0, 1)))
            tf = min(t_, b)
            ch = min(0.3 * tf, 0.25 * Wi)
            self.add(Panel(CB, base, "panel", [[(xl, 0), (xr, 0), (xr, Hi), (xl, Hi)]],
                           lambda t: asm_cb(t) @ M, host.p2,
                           Hinge(host.T2 @ hinge_frame_2d((b, y0 + vc), (0, 1)),
                                 hinge_frame_2d((0, 0), (1, 0))), f"{lab}: picture"))
            self.add(Panel(f"{base}.Foot", base, "tab",
                           [[(xl + ch, -tf), (xr - ch, -tf), (xr, 0), (xl, 0)]],
                           lambda t: asm_tabB(t) @ M, host.p2, None, f"{lab}: foot"))
            ta = min(t_, a - 1.0, b)
            tc = min(t_, a)
            cha, chc = min(0.3 * ta, 0.25 * w), min(0.3 * tc, 0.25 * w)
            self.add(Panel(f"{base}.TabA", strip, "tab",
                           [[(-ta, cha), (0, 0), (0, w), (-ta, w - cha)]], asm_tabA,
                           host.p1, None, f"{lab}: bridge tab on the background"))
            self.add(Panel(AC, strip, "panel", [[(0, 0), (b, 0), (b, w), (0, w)]], asm_ac,
                           host.p1, Hinge(host.T1 @ hinge_frame_2d((-a, y0), (0, 1)),
                                          hinge_frame_2d((0, 0), (0, 1))), f"{lab}: bridge"))
            self.add(Panel(f"{base}.TabC", strip, "tab",
                           [[(b, 0), (b + tc, chc), (b + tc, w - chc), (b, w)]],
                           lambda t: asm_cb(t) @ under, CB, None,
                           f"{lab}: bridge tab on the picture"))
            Mi = M.inverted()
            TA = Matrix.Translation((0.0, -y0, 0.0))
            TC1, TC2 = Matrix.Translation((b, -y0, 0.0)), Mi @ Matrix.Translation((b, -y0, 0.0))
            TB = Mi @ Matrix.Translation((a + b, -y0, 0.0))
        else:
            # picture pattern: x along the fold, y out from the background
            # (x runs down the fold here: it starts at the leg's start all the same)
            M = Matrix(((0, 1, 0, 0), (-1, 0, 0, vc), (0, 0, 1, 0), (0, 0, 0, 1)))
            xl, xr = vc - Wi, vc
            tf = min(t_, a)
            ch = min(0.3 * tf, 0.25 * Wi)
            self.add(Panel(f"{base}.TabA", base, "tab",
                           [[(xl, 0), (xl + ch, -tf), (xr - ch, -tf), (xr, 0)][::-1]],
                           lambda t: asm_tabA(t) @ M, host.p1, None,
                           f"{lab}: tab on the background"))
            self.add(Panel(AC, base, "panel", [[(xl, 0), (xr, 0), (xr, Hi), (xl, Hi)]],
                           lambda t: asm_ac(t) @ M, host.p1,
                           Hinge(host.T1 @ hinge_frame_2d((-a, y0 + vc), (0, 1)),
                                 hinge_frame_2d((0, 0), (-1, 0))), f"{lab}: picture"))
            tc = min(t_, b)
            tb = min(t_, b)
            chc, chb = min(0.3 * tc, 0.25 * w), min(0.3 * tb, 0.25 * w)
            self.add(Panel(CB, strip, "panel", [[(b, 0), (a + b, 0), (a + b, w), (b, w)]],
                           asm_cb, host.p2,
                           Hinge(host.T2 @ hinge_frame_2d((b, y0), (0, 1)),
                                 hinge_frame_2d((a + b, 0), (0, 1))), f"{lab}: leg"))
            self.add(Panel(f"{base}.TabC", strip, "tab",
                           [[(b - tc, chc), (b, 0), (b, w), (b - tc, w - chc)]],
                           lambda t: asm_ac(t) @ under, AC, None, f"{lab}: leg tab under "
                           f"the picture"))
            self.add(Panel(f"{base}.Foot", strip, "tab",
                           [[(a + b, 0), (a + b + tb, chb), (a + b + tb, w - chb), (a + b, w)]],
                           asm_tabB, host.p2, None, f"{lab}: leg foot"))
            Mi = M.inverted()
            TA = Mi @ Matrix.Translation((0.0, -y0, 0.0))
            TC1 = Mi @ Matrix.Translation((b, -y0, 0.0))
            TC2 = Matrix.Translation((b, -y0, 0.0))
            TB = Matrix.Translation((a + b, -y0, 0.0))
        for key, p1, T1, p2, T2, txt in (
                ("A", host.p1, host.T1 @ Matrix.Translation((-a, 0.0, 0.0)), AC, TA, "on top"),
                ("C", AC, TC1, CB, TC2, "inset"),
                ("B", CB, TB, host.p2, host.T2 @ Matrix.Translation((b, 0.0, 0.0)), "in front")):
            h = Host(self, p1, 0.0, 0.0, p2, 0.0, 0.0, f"{lab}: {txt}", T1, T2).finish()
            h.trig = host.trig
            self.hosts[(uid, key)] = h
