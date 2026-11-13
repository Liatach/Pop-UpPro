"""Pop-up card kinematics.

The card lies in its flat *pattern* space: spine along +Y from y = 0 to H,
left page at x in [-W, 0], right page at x in [0, W], printed (inside) face
towards +Z. The open angle t runs 0 (closed) to 180 degrees (flat).

Every panel has
  * polys      flat pattern polygons (mm, in its piece's pattern space)
  * asm(t)     4x4 matrix: pattern space -> assembled card space at angle t
  * parent     the panel it hangs from in the rig (None for the two pages)
  * hinge      fold it turns about relative to its parent, or None when it is
               glued (fixed) to its parent

Hinges are either LINEAR (the fold angle changes linearly with t: pages and
box folds) or SPHERICAL (V-folds: four fold lines through one point). For
both, `hinge_expression` returns a Blender driver expression in `t` (degrees)
that uses only functions Blender's simple-expression evaluator understands,
so the rig works without enabling Python scripts.

The Model class below sets a card up, builds each mechanism and checks the
result. What it builds with is in base.py (Panel, Hinge, Piece, Host); each
family of mechanisms has its own module (boxes, vfolds, zigzags, folds45,
standups, cubes, tubes, towers, collars, roofs, stage, tethers, flaps), a
class of builder methods mixed into Model; solver.py turns the solved
geometry into hinges the rig can follow.
"""
import math

from mathutils import Matrix, Vector

from .boxends import BoxEnds
from .boxes import BoxFolds
from .collars import Collars
from .cubes import Cubes
from .faces import Faces
from .flaps import Flaps
from .folds45 import Folds45
from .geom import Z, ccw, clip_halfplane, frame, hinge_frame_2d, rot_y, v3
from .roofs import Roofs
from .solver import Solver
from .stage import Stages
from .standups import StandUps
from .tethers import Tethers
from .towers import Towers
from .tubes import Tubes
from .vfolds import VFolds
from .zigzags import ZigZags
# everything that used to live in this module is still importable from it
from .base import (arcade, _card, CARD_PRESETS, CORNERS, halfplanes, Hinge, Host, IN, NO_HOST,  # noqa: F401
                   Panel, Piece, poly_area, round_arc, ROUND_DMAX, ROUND_FACETS, ROUND_FMAX,
                   _round_peak, _round_reach, SAMPLES, split_convex, T_MIN, TAB_LIFT,
                   unit2)


class Model(BoxFolds, BoxEnds, Faces, Folds45, StandUps, VFolds, ZigZags, Cubes, Tubes, Towers, Collars,
            Roofs, Stages, Tethers, Flaps, Solver):
    def __init__(self, card, mechs):
        self.card = dict(card)
        self.W = float(card["W"])
        self.H = float(card["H"])
        self.hold = card.get("hold", "RIGHT")
        self.panels = {}
        self.pieces = {}
        self.order = []  # panel names, parents before children
        self.warnings = []
        self.mechs = [dict(m) for m in mechs]
        self._branch = {}
        self.joints = {}
        self.hosts = {}
        self.placed = {}  # mechanism uid -> the Host it was built on
        self.cut_panels = set()
        self.top_cut = set()  # V-fold halves cut to a point under a V-fold on top
        self.pull = {}  # flap uid -> pull 0..1 (the Pull slider)
        self.soft = set()  # panel pairs joined by a sliding bend, not a fold
        self.blend = {}  # bent panel -> (stiff a, stiff b, y at a, y at b): shown between
        self.fold_kind = {}  # panel pairs drawn as this fold however they're shown
        self.facets = set()  # panel pairs that are one curved sheet
        self.smooth_panels = set()  # panels shaded as curved paper
        self.collar_free = {}  # tower uid -> (collar floor, its free corner)
        self._rail_len = {}  # collar railing -> its length along its floor
        self.flaps = {}  # flap uid -> info for the UI and checks
        self.tubes = {}  # tube uid -> plan geometry for tethers
        self.tethers = {}
        self.frames = {}  # stage frame uid -> info
        self.stack_ok = set()  # mechanism label pairs whose tabs may overlap
        self.floors = []  # floor / ceiling uids built so far (frames clear them)
        self.edge_tab = {}  # floor ("bottom") / ceiling ("top") tab widths
        # mechanism uid -> (piece, pattern -> its line coordinates, bounds) for
        # drawn creases and cuts
        self.line_frames = {}
        self.doors = list(card.get("doors") or [])
        self.doors_done = set()
        # A carousel stage only ever opens to 360/n degrees; everything is
        # sampled and checked up to there.
        self.tmax = min(180.0, float(card.get("tmax", 180.0)))
        self.samples = sorted({s for s in SAMPLES if s < self.tmax - 1e-6} |
                              {self.tmax, round(0.5 * self.tmax, 3)})
        self.t_ref = min(90.0, 0.5 * self.tmax)  # a typical open angle for setting things up
        self.TABLE_T = [T_MIN] + [float(d) for d in range(1, int(math.ceil(self.tmax)))] + \
            [self.tmax]
        self._build()
        self.solve_hinges()

    # ----------------------------------------------------------------- pages
    def gammas(self, t):
        """Rotation of the left and right page about the spine (radians)."""
        b = math.radians(180.0 - t)
        if self.hold == "SYM":
            return 0.5 * b, 0.5 * b
        if self.hold == "LEFT":
            return 0.0, b
        return b, 0.0  # RIGHT page stays flat

    def page_asm(self, side):
        if side == "L":
            return lambda t: rot_y(self.gammas(t)[0])
        return lambda t: rot_y(-self.gammas(t)[1])

    # ------------------------------------------------------------ add things
    def add_piece(self, piece):
        self.pieces[piece.name] = piece
        return piece

    def add(self, panel):
        if not panel.polys and not getattr(panel, "helper", False):
            return None
        self.panels[panel.name] = panel
        self.pieces[panel.piece].panels.append(panel.name)
        self.order.append(panel.name)
        return panel

    def warn(self, msg):
        if msg not in self.warnings:
            self.warnings.append(msg)

    def carve(self, piece, region, allowed, lab):
        """Cut a convex region (pattern coords) out of a piece's panels.
        Returns the cut-out cells, or None (with a warning) if the region
        is not wholly on the allowed panels."""
        region = ccw(region)
        hps = halfplanes(region)
        want = poly_area(region)
        keep, got, total = {}, {}, 0.0
        for name in self.pieces[piece].panels:
            p = self.panels[name]
            outs, ins = [], []
            for poly in p.polys:
                o, i = split_convex(poly, hps)
                outs += o
                ins += i
            if ins and name not in allowed:
                self.warn(f"{lab}: overlaps {p.label.split(':')[0]}; skipped")
                return None
            keep[name], got[name] = outs, ins
            total += sum(poly_area(q) for q in ins)
        if abs(total - want) > max(0.5, 0.002 * want):
            self.warn(f"{lab}: does not fit on what it is cut from; skipped")
            return None
        for name, outs in keep.items():
            if got[name]:
                self.panels[name].polys = [ccw(q) for q in outs]
                if not outs and self.panels[name].kind != "page":
                    self.warn(f"{lab}: uses up all of {self.panels[name].label}; make it "
                              f"smaller than its host so there's paper left round it")
        return [q for qs in got.values() for q in qs]

    @staticmethod
    def split_cells(cells, n, d):
        """Cells on each side of a line: (n . p >= d, n . p <= d)."""
        a, b = [], []
        for c in cells:
            p = clip_halfplane(c, n, d)
            q = clip_halfplane(c, (-n[0], -n[1]), -d)
            if len(p) >= 3 and abs(poly_area(p)) > 1e-6:
                a.append(p)
            if len(q) >= 3 and abs(poly_area(q)) > 1e-6:
                b.append(q)
        return a, b

    # ----------------------------------------------------------------- build
    def _build(self):
        W, H = self.W, self.H
        card = self.add_piece(Piece("Card", "Card", 0, (0.0, H / 2), True))
        card.size = (2 * W, H)
        self.add(Panel("Page.L", "Card", "page", [[(-W, 0), (0, 0), (0, H), (-W, H)]],
                       self.page_asm("L"), None,
                       Hinge(Matrix.Identity(4), Matrix.Identity(4)), "Left page"))
        self.add(Panel("Page.R", "Card", "page", [[(0, 0), (W, 0), (W, H), (0, H)]],
                       self.page_asm("R"), None,
                       Hinge(Matrix.Identity(4), Matrix.Identity(4)), "Right page"))
        self.hosts[(0, "S")] = Host(self, "Page.L", 0.0, 0.0, "Page.R", 0.0, 0.0,
                                    "Card spine").finish()
        self.hosts[(0, "S")].key = 0

        # parents (hosts) before children; drop cycles and missing hosts
        by_uid = {m["uid"]: m for m in self.mechs}
        order, state = [], {}

        def visit(m):
            st = state.get(m["uid"])
            if st == 2:
                return True
            if st == 1:
                return False
            state[m["uid"]] = 1
            h = m.get("host", 0) if m["type"] not in NO_HOST else 0
            ok = True
            if m["type"] == "PICTURE" and m.get("host"):
                d_ = by_uid.get(m["host"])
                if d_ is None:
                    self.warn(f"{m['label']}: what it's glued on is missing; skipped")
                    ok = False
                elif not visit(d_):
                    ok = False
            if m["type"] == "TETHER":
                deps = [m.get("from_uid", 0)]
                if m.get("to") == "TUBE":
                    deps.append(m.get("to_uid", 0))
                for dep in deps:
                    d_ = by_uid.get(dep)
                    if d_ is None or d_["type"] != "TUBE":
                        self.warn(f"{m['label']}: pick the tube(s) it joins; skipped")
                        ok = False
                    elif not visit(d_):
                        ok = False
            if h:
                parent = by_uid.get(h)
                lid = parent is not None and parent["type"] == "TUBE" and \
                    parent.get("roof") == "FLAT" and parent.get("roof_fold") == "DIP"
                stage = parent is not None and parent["type"] == "STAGE"
                joint = parent is not None and parent["type"] in ("FLOOR", "CEILING")
                ffc = m["type"] in ("FRAME", "FLOOR", "CEILING")
                if joint and m.get("vside") == "V" and m["type"] != "VFOLD":
                    self.warn(f"{m['label']}: only V-folds stand on a floor's or ceiling's "
                              f"crease (it is a mountain fold from the stage side); use its "
                              f"corners for boxes and cubes; skipped")
                    ok = False
                elif parent is not None and (stage != ffc or (joint and ffc)):
                    self.warn(f"{m['label']}: frames, floors and ceilings go on a stage set, "
                              f"and only they do; skipped")
                    ok = False
                elif parent is not None and parent["type"] in ("VFOLD", "ZIGZAG", "QUADS") and (
                        m["type"] not in ("STANDUP", "BOX", "VFOLD", "MOUTH", "CUBE",
                                          "TUBE", "PYRAMID", "JACK") or
                        (m.get("vside", "FL") != "V" and
                         (m["type"] not in ("STANDUP", "BOX", "CUBE", "TUBE", "VFOLD",
                                            "PYRAMID")
                          or m.get("style") == "CUT"))):
                    self.warn(f"{m['label']}: on a V-fold's crease go boxes, box layers, "
                              f"V-folds, mouths, cubes, tubes and stand-ups; in front of or "
                              f"behind a half stand-ups, glued boxes, cubes, tubes and "
                              f"V-folds; skipped")
                    ok = False
                elif parent is None or (parent["type"] not in ("BOX", "STANDUP", "VFOLD",
                                                               "CUBE", "PLATFORM", "ZIGZAG",
                                                               "QUADS")
                                        and not lid and not stage and not joint
                                        and not (parent["type"] == "TUBE" and
                                                 m.get("wall") in ("L", "R") + CORNERS)):
                    if parent is not None and parent["type"] == "TUBE":
                        self.warn(f"{m['label']}: {parent['label']} has no roof crease to "
                                  f"stand on (give it a Flat roof with a Dip, or pick a "
                                  f"wall as the Fold); skipped")
                    else:
                        self.warn(f"{m['label']}: its host is missing (a box, or a tube "
                                  f"with a dipped flat roof); skipped")
                    ok = False
                elif parent["type"] == "TUBE" and m.get("wall") in CORNERS and (
                        m["type"] != "BOX" or m.get("style") == "CUT"):
                    self.warn(f"{m['label']}: only glued box folds (towers) stand in a "
                              f"tube's inside corners; skipped")
                    ok = False
                elif not visit(parent):
                    self.warn(f"{m['label']}: hosts form a loop; skipped")
                    ok = False
            state[m["uid"]] = 2
            if ok:
                order.append(m)
            else:
                m["_skip"] = True
            return ok

        # floors and ceilings first: frames are cut to clear them
        for m in sorted(self.mechs, key=lambda m: 0 if m["type"] in ("FLOOR", "CEILING") else 1):
            visit(m)
        for m in order:
            h = m.get("host", 0) if m["type"] not in NO_HOST else 0
            fold = m.get("fold", "A")
            if m["type"] == "PICTURE":
                self._picture(m)
                continue
            if h and by_uid[h]["type"] == "TUBE":
                # a side wall's foot, or the roof's centre crease
                w_ = m.get("wall", "NONE")
                fold = w_ if w_ in CORNERS else {"L": "WL", "R": "WR"}.get(w_, "R")
            if h and by_uid[h]["type"] == "CUBE":
                fold = "WR" if m.get("wall") == "R" else "WL"  # a front wall's foot
            if h and by_uid[h]["type"] == "STAGE":
                fold = "S"  # the stage set's back crease
            if h and by_uid[h]["type"] == "PLATFORM":
                fold = "A"  # the valley in its top
            if h and by_uid[h]["type"] in ("FLOOR", "CEILING"):
                fold = "L" if m.get("side", "L") == "L" else "R"  # its join with a wall
                if m.get("vside") == "V":
                    fold = "V"  # on its centre crease, from the stage side
            if h and by_uid[h]["type"] in ("VFOLD", "ZIGZAG", "QUADS"):
                fold = m.get("vside", "FL")  # in front of / behind a half
            if h and fold == "V" and by_uid[h]["type"] == "BOX":
                # a strap's valley between two peaks, counted from the left
                host = self.hosts.get((h, f"V{int(m.get('gully', 1) or 1)}"))
            else:
                host = self.hosts.get((h, fold) if h else (0, "S"))
            if host is None:
                hm = by_uid.get(h) if h else None
                if hm is not None and hm["uid"] in self.placed and \
                        hm["type"] in ("VFOLD", "ZIGZAG", "QUADS") and fold != "V":
                    self.warn(f"{m['label']}: {hm['label']} has no glue folds to stand on "
                              f"(its halves aren't glued along a line); put it on the crease")
                elif hm is not None and hm["uid"] in self.placed and hm["type"] == "BOX":
                    # the box is there; the fold asked for isn't
                    if abs(float(hm.get("fan_angle", 0.0) or 0.0)) > 0.05:
                        why = "is an angled box fold, which nothing stands on yet"
                    elif fold == "V":
                        why = ("has no valley to stand in (a strap with two or more Peaks "
                               "has); pick another Fold")
                    elif fold == "C":
                        why = ("has no inset fold (with several Peaks its top doesn't meet "
                               "its front); pick a Valley")
                    else:
                        why = "has no such fold"
                    self.warn(f"{m['label']}: {hm['label']} {why}; skipped")
                else:
                    self.warn(f"{m['label']}: its host was skipped; skipped too")
                continue
            self.placed[m["uid"]] = host  # the fold it stands on (Align measures along it)
            n0 = len(self.order)
            if m["type"] == "VFOLD":
                if m.get("cut_above"):
                    self._cut_above(m, host)
                self._vfold(m, host)
            elif m["type"] == "MOUTH":
                self._mouth(m, host)
            elif m["type"] == "BOX":
                self._box(m, host)
            elif m["type"] == "STANDUP":
                self._standup(m, host)
            elif m["type"] == "PLATFORM":
                self._platform(m, host)
            elif m["type"] == "RISER":
                self._riser(m, host)
            elif m["type"] == "BOXEND":
                self._boxend(m, host)
            elif m["type"] == "DOUBLE45":
                self._double45(m, host)
            elif m["type"] == "ZIGZAG":
                self._zigzag(m, host)
            elif m["type"] == "QUADS":
                self._quads(m, host)
            elif m["type"] == "JACK":
                self._jack(m, host, bool(h) and by_uid[h]["type"] == "VFOLD")
            elif m["type"] == "CUBE":
                self._cube(m, host)
            elif m["type"] == "FLAP":
                self._flap(m)
            elif m["type"] == "TUBE":
                self._tube(m, host)
            elif m["type"] == "TETHER":
                self._tether(m)
            elif m["type"] == "PYRAMID":
                self._pyramid(m, host)
            elif m["type"] == "STAGE":
                self._stage(m, host)
            elif m["type"] == "ROOF":
                self._roof_stage(m, host)
            elif m["type"] == "FRAME":
                self._frame(m, host)
            elif m["type"] in ("FLOOR", "CEILING"):
                self._floor(m, host)
            if isinstance(host.key, tuple):
                # standing in a floor's corner its tabs may lie over the
                # floor's own tab along the wall: glue on glue is fine
                self.stack_ok.add(frozenset((by_uid[h]["label"], m["label"])))
            if not host.trig:
                # the host's panels don't turn with the card's own angle, so
                # no closed form applies: every new fold is tabulated
                for name in self.order[n0:]:
                    hg = self.panels[name].hinge
                    if hg is not None and hg.kind in ("LINEAR", "SPHERICAL", "EXPR"):
                        hg.kind = "TABLE"
                    if hg is not None:
                        hg.host_bound = True  # rides a fold that may not open evenly
        self._card_lines()

    def _door_lines(self, piece, names, primary):
        """Door flaps cut in these panels, as extra lines in the pattern. A
        door on a face goes with the panels holding that face; a door on the
        whole piece with the piece's own creases (primary)."""
        from .openings import door_lines
        out = []
        for d in self.doors:
            if d["id"] in self.doors_done or (d.get("piece") or "Card") != piece:
                continue
            face = d.get("face") or ""
            if face:
                if face not in names or (face.startswith("Page.") and not primary):
                    continue
            elif not primary:
                continue
            out += door_lines(self, d)
            self.doors_done.add(d["id"])
        return out

    def _card_lines(self):
        """Extra creases and cuts in the card itself (the background): a
        ceiling or floor folded out of the pages, cut-out shapes. Pattern x
        across the card (left page negative), y up the spine."""
        self.line_frames[0] = ("Card", lambda q: q, None)
        lines = self.card.get("lines")
        from .folds import build as fold_build, expand
        doors = self._door_lines("Card", ["Page.L", "Page.R"], True)
        if lines or doors:
            fold_build(self, "Card", ["Page.L", "Page.R"], "Card", expand(lines) + doors,
                       "Card", float(self.card.get("pleat", 0.0) or 0.0))
        for d in self.doors:
            if d["id"] not in self.doors_done:
                self.warn(f"Door flap on {d.get('piece') or 'Card'}: door flaps work on the "
                          f"card, V-folds, box folds and box layers; cut as a hole")

    # ------------------------------------------------------- page directions
    def dirs(self, t):
        L, R = self.panels["Page.L"].asm(t), self.panels["Page.R"].asm(t)
        l = L.to_3x3() @ Vector((-1, 0, 0))
        r = R.to_3x3() @ Vector((1, 0, 0))
        return l, r, L.to_3x3() @ Z, R.to_3x3() @ Z

    def _wall_host(self, uid, key, wall, w_org, w_foot, w_up, page, Tp, p_org, p_foot,
                   p_out, label, size):
        """The fold where a wall standing on a page meets it, seen from
        outside: the wall is the background (virtual left page), the page
        the floor beyond it (virtual right). Positions run along the wall's
        foot from w_org (p_org on the page). Like a V-fold's glue folds,
        what stands here is tabulated."""
        if wall not in self.panels or page not in self.panels:
            return None
        T1 = frame(Vector((w_org[0], w_org[1], 0.0)), -Vector((w_up[0], w_up[1], 0.0)),
                   Vector((w_foot[0], w_foot[1], 0.0)))
        T2 = Tp @ frame(Vector((p_org[0], p_org[1], 0.0)), Vector((p_out[0], p_out[1], 0.0)),
                        Vector((p_foot[0], p_foot[1], 0.0)))
        h = Host(self, wall, 0.0, 0.0, page, 0.0, 0.0, label, T1, T2).finish()
        h.trig = False
        h.size = size
        h.key = (uid, key)
        self.hosts[(uid, key)] = h
        return h

    def _glue_asm(self, target, src_asm, e0, e1, side_src, side_tgt, below=False,
                  t=None):
        """Placement for a tab hanging off edge e0-e1 of a panel (placed by
        src_asm) that folds over and glues flat on target, on the side_tgt
        side of that edge (target pattern), on its back if below."""
        t = min(90.0, 0.5 * self.tmax) if t is None else t
        Rel = target.asm(t).inverted() @ src_asm(t)
        q0, q1 = Rel @ v3(e0), Rel @ v3(e1)
        q0.z = q1.z = 0.0
        for q in (q0, q1):  # a doubled layer sits a hair off the fold: put it on it
            if abs(q.x) < 0.5:
                q.x = 0.0
        Fp = frame(v3(e0), v3((e1[0] - e0[0], e1[1] - e0[1])), v3(side_src))
        Fq = frame(q0, q1 - q0, v3(side_tgt))
        A = Matrix.Translation((0, 0, -TAB_LIFT if below else TAB_LIFT)) @ Fq @ Fp.inverted()
        return lambda t, f=target.asm, A=A: f(t) @ A

    def _hinge_on(self, parent, asm, c0, c1, t=None):
        """Hinge for a panel (pattern fold line c0 -> c1, placed by asm) on a
        parent panel: the same line found in the parent's pattern."""
        t = min(90.0, 0.5 * self.tmax) if t is None else t
        Rel = self.panels[parent].asm(t).inverted() @ asm(t)
        p0, p1 = Rel @ v3(c0), Rel @ v3(c1)
        return Hinge(hinge_frame_2d(p0[:2], (p1 - p0)[:2]),
                     hinge_frame_2d(c0, (c1[0] - c0[0], c1[1] - c0[1])), "TABLE", {})

    # ------------------------------------------------------------- checks
    @staticmethod
    def _overlap(a, b):
        r = list(a)
        for n, d in halfplanes(ccw(b)):
            r = clip_halfplane(r, n, d)
            if len(r) < 3:
                return 0.0
        return abs(poly_area(r))

    def check_overlaps(self):
        """Glue tabs and cut-outs that land on the same paper must not overlap
        each other, and tabs must land on paper (not on a hole)."""
        prints = {}  # piece -> [(mechanism label, kind, convex poly in pattern)]
        for name in self.order:
            p = self.panels[name]
            lab = p.label.split(":")[0].replace(" (inset)", "")
            if p.kind == "tab":
                host = self.panels[p.parent]
                M = host.asm(self.t_ref).inverted() @ p.asm(self.t_ref)
                for poly in p.polys:
                    q = [(M @ v3(c)).to_2d()[:] for c in poly]
                    # which face of the host it is glued to (printed or back)
                    face = 1 if (M @ v3(poly[0])).z >= 0 else -1
                    prints.setdefault(host.piece, []).append((lab, "tab", q, host, face))
            elif name in self.cut_panels:
                for poly in p.polys:
                    prints.setdefault(p.piece, []).append((lab, "cut", poly, p, 0))
        for piece, items in prints.items():
            for i, (la, ka, pa, ha, fa) in enumerate(items):
                if ka == "tab":
                    on = sum(self._overlap(pa, q) for q in ha.polys)
                    if on < abs(poly_area(pa)) - 1.0:
                        self.warn(f"{la}: a glue tab hangs off {ha.label.split(':')[0]}")
                for lb, kb, pb, hb, fb in items[i + 1:]:
                    if {ka, kb} == {"tab", "cut"} and (ha if ka == "tab" else hb) is \
                            (hb if ka == "tab" else ha):
                        continue  # a tab glued onto that very cut-in panel
                    if ka == kb == "tab" and fa != fb:
                        continue  # glued to opposite faces of the paper
                    if la != lb and frozenset((la, lb)) not in self.stack_ok and \
                            self._overlap(pa, pb) > 1.0:
                        self.warn(f"{la} and {lb} overlap on the paper")

    def check_fit(self):
        """Panels must stay between the pages and inside the card outline."""
        self.check_overlaps()
        W, H = self.W, self.H
        for name in self.order:
            p = self.panels[name]
            if p.kind != "panel" or p.outside:
                continue
            lab = p.label.split(":")[0]
            pts = [v3(q) for poly in p.polys for q in poly]
            poke = None
            tol = max(0.5, getattr(p, "rub", 0.0))  # (walls let rub a little on purpose)
            for t in self.samples:
                M = p.asm(t)
                l, r, nl, nr = self.dirs(t)
                for q in pts:
                    w = M @ q
                    if w.dot(nl) < -tol or w.dot(nr) < -tol:
                        poke = t if poke is None else max(poke, t)
                        break
            if poke is not None:
                self.warn(f"{lab}: pokes through the card around {poke:.0f} degrees")
            M = p.asm(0.5)
            l, r, nl, nr = self.dirs(0.5)
            for q in pts:
                w = M @ q
                if w.y < -0.5 or w.y > H + 0.5 or max(w.dot(l), w.dot(r)) > W + 0.5:
                    self.warn(f"{lab}: sticks out of the card when closed")
                    break
