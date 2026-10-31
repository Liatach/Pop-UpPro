import math

import bpy
from bpy.props import (BoolProperty, CollectionProperty, EnumProperty,
                       FloatProperty, FloatVectorProperty, IntProperty, PointerProperty,
                       StringProperty)

from . import live
from .images import PopupImage


def _changed(self, context):
    live.schedule(context.scene)


def _redraw(self, context):
    wm = getattr(context, "window_manager", None) if context else None
    for win in (wm.windows if wm else []):
        for area in win.screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()


def _sym(self, context):
    if self.symmetric:
        self["phi_r"] = self.phi_l
        self["alpha_r"] = self.alpha_l
    elif self.get("glue_r", 0.0) <= 0.0:
        self["glue_r"] = self.glue  # start the right side as long as the left
    live.schedule(context.scene)


KINDS = [
    ("VFOLD", "V-fold", "Two halves glued along a V across a fold", "MOD_TRIANGULATE", 0),
    ("BOX", "Box fold", "Separate strip glued across a fold (parallel fold)", "MESH_CUBE", 1),
    ("BOXCUT", "Box layer", "Parallel fold cut out of the paper itself", "SNAP_FACE", 2),
    ("MOUTH", "Mouth", "Slit and two pairs of triangles cut into the paper; the jaws "
     "open as the card opens", "MOD_SIMPLEDEFORM", 3),
    ("CUBE", "Cube (180°)", "Box standing on one corner edge on the fold; rises as a "
     "card opens flat", "CUBE", 4),
    ("FLAP", "Flap", "Lift-the-flap worked by a pull tab, with its own Pull control",
     "MOD_CLOTH", 5),
    ("TUBE", "Tube", "Hexagon, box or recessed tube standing on two parallel strips "
     "either side of the fold", "MESH_CYLINDER", 6),
    ("TETHER", "Tether", "Wall from a tube's corner or crease to another tube or to a foot "
     "on a strip; pulled open by the tubes", "LINKED", 7),
    ("PYRAMID", "Pyramid", "Pyramid or tent standing on two parallel strips either side "
     "of the fold", "CONE", 8),
    ("FRAME", "Frame", "Stage frame across a carousel stage, glued to both pages; pulls "
     "flat when the stage is fully open", "IMAGE_PLANE", 9),
    ("FLOOR", "Floor", "Stage floor along the bottom edges of the pages", "TRIA_DOWN_BAR", 10),
    ("CEILING", "Ceiling", "Stage ceiling along the top edges of the pages", "TRIA_UP_BAR",
     11),
    ("STAGE", "Stage Set", "A stage standing in the card as a V-fold, with frames and a "
     "ceiling inside it (Birmingham 118)", "IMAGE_BACKGROUND", 12),
    ("STANDUP", "Stand-up", "A picture held up off the background by a small bridge, or "
     "flat on a leg (parallelogram stand-up, Birmingham 38)", "OUTLINER_OB_IMAGE", 13),
    ("ROOF", "Roof", "A peaked roof: the background is cut to a gable and a V-fold glued "
     "along its eaves rises to a ridge, level when the card or stage is fully open",
     "HOME", 14),
]

POINTS = [
    ("FL", "Front Left", "Front corner of the left side", "", 0),
    ("FR", "Front Right", "Front corner of the right side", "", 1),
    ("BL", "Back Left", "Back corner of the left side", "", 2),
    ("BR", "Back Right", "Back corner of the right side", "", 3),
    ("CF", "Front Crease", "Crease of the front pair, above the fold", "", 4),
    ("CB", "Back Crease", "Crease of the back pair, above the fold", "", 5),
]

_tube_items = []


def tube_items(self, context):
    global _tube_items
    items = [("0", "(pick a tube)", "", "", 0)]
    st = context.scene.popup if context and context.scene else None
    if st is not None:
        for m in st.mechs:
            if m.kind == "TUBE":
                items.append((str(m.uid), m.label, "", "MESH_CYLINDER", m.uid))
    _tube_items = items
    return _tube_items


def _get_from(self):
    return self.from_uid


def _set_from(self, v):
    self.from_uid = v
    live.schedule(bpy.context.scene)


def _get_to(self):
    return self.to_uid


def _set_to(self, v):
    self.to_uid = v
    live.schedule(bpy.context.scene)

FOLDS = [
    ("A", "On Top", "Sits on the box's top, against the back panel (step up)", "TRIA_UP", 0),
    ("B", "In Front", "Sits on the floor panel, against the box's front (step forward)",
     "TRIA_DOWN", 1),
    ("C", "Inset", "Pushed into the box's outer corner: a valley fold, opening inside "
     "the box", "TRIA_LEFT", 2),
    ("V", "Valley", "Between two peaks of a strap with several (Gully picks which)",
     "IPO_EASE_IN_OUT", 3),
]

_host_items = []


def _descendants(mechs, uid):
    out, frontier = set(), {uid}
    while frontier:
        nxt = {m.uid for m in mechs if m.host_uid in frontier and m.uid not in out}
        out |= nxt
        frontier = nxt
    return out


def host_items(self, context):
    global _host_items
    items = [("0", "Card Spine", "Sit on the card's centre fold", "SNAP_MIDPOINT", 0)]
    st = context.scene.popup if context and context.scene else None
    if st is not None:
        bad = _descendants(st.mechs, self.uid) | {self.uid}
        for m in st.mechs:
            if self.kind in ("FLAP", "TETHER", "PYRAMID", "ROOF") or m.uid in bad:
                continue
            if self.kind in ("FRAME", "FLOOR", "CEILING"):
                if m.kind == "STAGE":
                    items.append((str(m.uid), m.label, f"Stand in {m.label}",
                                  "IMAGE_BACKGROUND", m.uid))
                continue
            if m.kind == "VFOLD" and self.kind in ("STANDUP", "BOX", "BOXCUT", "VFOLD",
                                                   "MOUTH", "CUBE", "TUBE"):
                items.append((str(m.uid), m.label, f"On {m.label}: its crease, or in "
                              f"front of or behind a half", "MOD_TRIANGULATE", m.uid))
            elif m.kind in ("BOX", "BOXCUT", "STANDUP"):
                items.append((str(m.uid), m.label, f"Sit on a fold of {m.label}",
                              "MESH_CUBE" if m.kind != "STANDUP" else "OUTLINER_OB_IMAGE",
                              m.uid))
            elif m.kind in ("FLOOR", "CEILING"):
                items.append((str(m.uid), m.label, f"Sit in the corner where {m.label} "
                              f"meets a wall", "TRIA_DOWN_BAR" if m.kind == "FLOOR"
                              else "TRIA_UP_BAR", m.uid))
            elif m.kind in ("CUBE", "TUBE") and self.kind in ("STANDUP", "BOX", "CUBE",
                                                               "TUBE", "VFOLD"):
                items.append((str(m.uid), m.label, f"Stand outside a wall of {m.label}, "
                              f"where it meets the page" + (", or on its roof's crease"
                                                            if m.kind == "TUBE" else ""),
                              "CUBE" if m.kind == "CUBE" else "MESH_CYLINDER", m.uid))
            elif m.kind == "TUBE" and m.roof == "FLAT" and m.roof_fold == "DIP":
                items.append((str(m.uid), f"{m.label} roof", f"Sit on the centre crease of "
                              f"{m.label}'s roof", "MESH_CYLINDER", m.uid))
    _host_items = items
    return _host_items


def _host_get(self):
    return self.host_uid


def fit_to_host(m, st):
    """Size a mechanism to sit inside the host-box fold it was just put on:
    half the host's panels, centred along it, so there's paper left round it
    to read as a step or an inset."""
    host = next((h for h in st.mechs if h.uid == m.host_uid), None)
    if host is not None and host.kind in ("FLOOR", "CEILING"):
        # in the corner: clear of the floor's own tab along the wall
        k = max(host.tab + 12.0 + 3.0, 0.15 * host.depth)
        was = st.live
        st["live"] = False
        try:
            if m.kind in ("BOX", "BOXCUT"):
                m.height = m.depth = k
                m.width = 0.25 * host.depth
                m.y = 0.3 * host.depth
            elif m.kind == "VFOLD":
                m.height = m.glue = 0.8 * k
                m.y = 0.4 * host.depth
            elif m.kind == "CUBE":
                m.size = m.height = 0.6 * k
                m.y = 0.3 * host.depth
        finally:
            st["live"] = was
        return
    if host is not None and host.kind == "VFOLD":
        # on a half's glue line: the half is the background, the page the floor
        was = st.live
        st["live"] = False
        try:
            g, L = host.glue, host.height
            if m.vside == "V":  # on the crease: the halves are its pages
                k = 0.35 * min(g, L)
                if m.kind in ("BOX", "BOXCUT"):
                    m.height = m.depth = k
                    m.width = 0.35 * L
                    m.y = 0.3 * L
                elif m.kind == "VFOLD":
                    m.glue = m.height = k
                    m.y = 0.3 * L
                elif m.kind == "STANDUP":
                    m.height, m.depth, m.width = 0.6 * k, 0.6 * k, 0.2 * L
                    m.img_w, m.img_h = 0.4 * L, 1.2 * k
                    m.y = 0.4 * L
                elif m.kind == "MOUTH":
                    m.jaw = 0.6 * k
                    m.upper = m.lower = 0.15 * L
                    m.y = 0.5 * L
                elif m.kind == "CUBE":  # in the V, up the crease, clear of the page
                    m.size = m.height = 0.7 * k
                    m.y = 0.4 * L
                elif m.kind == "TUBE":
                    m.x, m.height = 0.25 * k, 0.7 * k
                    m.depth = 0.4 * L
                    m.front = m.back = 0.35 * k
                    m.y = 0.3 * L
                return
            # in front of (or behind) a half: the half is the background, the
            # page the floor, positions out along the glue line
            s_ = 0.25 * min(g, L)
            if m.kind == "CUBE":
                m.size = m.height = s_
                m.y = 0.2 * g
                return
            if m.kind == "TUBE":
                m.x, m.depth, m.height = 0.1 * g, 0.35 * g, 0.25 * L
                m.front = m.back = 0.15 * g
                m.y = 0.15 * g
                return
            if m.kind == "VFOLD":
                m.glue = m.height = s_
                m.y = 0.3 * g
                return
            if m.kind == "STANDUP":
                m.width = 0.3 * g
                m.y = 0.35 * g
                m.height = 0.35 * L
                m.depth = 0.25 * g
                m.img_w = 0.5 * g
                m.img_h = 0.6 * L
            elif m.kind == "BOX":
                m.width = 0.4 * g
                m.y = 0.3 * g
                m.height = m.depth = 0.25 * min(g, L)
        finally:
            st["live"] = was
        return
    if host is not None and host.kind in ("CUBE", "TUBE") and not (
            host.kind == "TUBE" and m.wall == "NONE" and host.roof == "FLAT"
            and host.roof_fold == "DIP"):
        # outside a wall, at its foot: the wall the background, the page the floor
        was = st.live
        st["live"] = False
        try:
            if m.wall == "NONE":
                m["wall"] = 1  # the left wall
            if host.kind == "CUBE":
                ww = host.size if m.wall == "L" or host.size_r <= 0 else host.size_r
            else:
                ww = host.depth
            k = 0.3 * min(ww, host.height)
            if m.kind == "CUBE":
                m.size, m.size_r, m.height = k, 0.0, k
            elif m.kind in ("BOX", "BOXCUT"):
                m.height = m.depth = k
                m.width = 0.4 * ww
            elif m.kind == "STANDUP":
                m.height = m.depth = 0.8 * k
                m.width = 0.25 * ww
                m.img_w, m.img_h = 0.5 * ww, 1.4 * k
            elif m.kind == "VFOLD":
                m.glue = m.height = k
            elif m.kind == "TUBE":
                _fit_tube(m, k, ww, 0.0)
            m.y = 0.3 * ww
        finally:
            st["live"] = was
        return
    if host is not None and host.kind == "STAGE":
        was = st.live
        st["live"] = False
        try:
            if m.kind == "FRAME":
                n = sum(1 for x in st.mechs if x.kind == "FRAME" and x.host_uid == host.uid)
                m.x = host.glue - 1.0 if n <= 1 else max(8.0, host.glue * (1 - 0.25 * (n - 1)))
                m.y, m.height = 0.0, host.height
            elif m.kind in ("FLOOR", "CEILING"):
                m.depth = host.glue
        finally:
            st["live"] = was
        return
    if host is None or host.kind not in ("BOX", "BOXCUT", "TUBE", "STANDUP"):
        return
    if host.kind == "TUBE":  # the roof's crease: a half each side, as long as the tube
        room, w = host.x, host.depth
    else:
        a, b, w = host.height, host.depth, host.width  # left page, right page, along spine
        room = {"A": b, "B": a, "C": min(a, b)}.get(m.fold, min(a, b))
    k = 0.5 * room
    was = st.live
    st["live"] = False
    try:
        if host.kind == "STANDUP":
            w = host.img_w  # the picture is what there is room on
            hy = host.y + 0.5 * host.width - 0.5 * w
        else:
            hy = host.y
            k_ = math.tan(math.radians(host.slant))  # a slanted strip's folds move up or down
            np_ = max(1, host.peaks) if host.kind == "BOX" else 1
            a_, b_ = host.height, host.depth
            if m.fold == "V" and np_ > 1:
                # a valley between two peaks: x where it lies when flat
                g_ = max(1, min(m.gully, np_ - 1))
                x_ = -a_ + g_ * (a_ + b_) / np_
                room = min(a_, b_) / np_
                k = 0.5 * room
                hy += k_ * x_
            else:
                hy += {"A": -k_ * a_, "B": k_ * b_, "C": k_ * (b_ - a_)}.get(m.fold, 0.0)
                if np_ > 1 and m.fold in ("A", "B"):
                    room = min(room, (b_ if m.fold == "A" else a_) / np_)
                    k = 0.5 * room
        if m.kind in ("BOX", "BOXCUT"):
            m.height = m.depth = k
            m.width = 0.5 * w
            m.y = hy + 0.25 * w
        elif m.kind == "STANDUP":
            m.height = m.depth = k
            m.width = 0.25 * w
            m.img_w = 0.5 * w
            m.img_h = 1.6 * k
            m.y = hy + 0.5 * w - 0.5 * m.width
        elif m.kind == "VFOLD":
            m.height = m.glue = 0.8 * k
            m.y = hy + 0.25 * w
        elif m.kind == "MOUTH":
            m.jaw = 0.6 * k
            m.upper = m.lower = min(0.25 * w, 0.6 * k)
            m.y = hy + 0.5 * w
        elif m.kind == "CUBE":
            m.size = m.height = 0.6 * k
            m.y = hy + 0.25 * w
        elif m.kind == "TUBE":
            _fit_tube(m, k, w, hy)
    finally:
        st["live"] = was


def _fit_tube(m, k, w, y0):
    """A tube sized to a host's fold: strips a little either side of it."""
    m.x = 0.35 * k
    m.height = 0.8 * k
    m.depth = 0.45 * w
    m.front = m.back = max(m.x, 0.45 * k)
    m.y = y0 + 0.25 * w


def _host_set(self, value):
    self.host_uid = value
    st = bpy.context.scene.popup
    if value:
        fit_to_host(self, st)
    live.schedule(bpy.context.scene)


def _fold_changed(self, context):
    if self.host_uid:
        fit_to_host(self, context.scene.popup)
    live.schedule(context.scene)


def _line_siblings(ln):
    path = ln.path_from_id()
    try:
        coll = ln.id_data.path_resolve(path[:path.rindex("[")])
    except (ValueError, AttributeError):
        return []
    return [x for x in coll if x.group == ln.group and x != ln]


def _line_expand(self, context):
    if self.group:
        for ln in _line_siblings(self):
            ln["expanded"] = self.expanded


def _line_xform(self, context):
    """Flip, Turn and Move act on the whole shape: every line added with it."""
    if self.group:
        for ln in _line_siblings(self):
            for k in ("flip", "turn", "move_x", "move_y"):
                ln[k] = getattr(self, k)
    live.schedule(context.scene)


class PopupLine(bpy.types.PropertyGroup):
    """An extra crease or cut on a V-fold piece, in the piece's own pattern:
    x across (the centre fold at 0, the left half negative), y up the centre
    fold from the V point (mm)."""
    kind: EnumProperty(name="Kind", items=[
        ("CREASE", "Crease", "Extra fold line"),
        ("CUT", "Cut", "Slit through the paper"),
        ("JOIN", "Join Tab", "A crease whose far side (towards the centre fold) is a "
         "glue tab: it is glued back to back with its mirror image, joining two parts "
         "cut apart at the centre (a peaked roof from the card)")], update=_changed)
    mirror: BoolProperty(name="Mirror", description="Copy the line onto the other half "
                         "(mirrored across the centre fold)", default=True, update=_changed)
    x0: FloatProperty(name="Start X", description="Across from the centre fold (mm, "
                      "left half negative)", default=0.0, soft_min=-150.0, soft_max=150.0,
                      update=_changed)
    y0: FloatProperty(name="Start Y", description="Up the centre fold from the V point (mm)",
                      default=30.0, soft_min=-50.0, soft_max=200.0, update=_changed)
    x1: FloatProperty(name="End X", default=-20.0, soft_min=-150.0, soft_max=150.0,
                      update=_changed)
    y1: FloatProperty(name="End Y", default=20.0, soft_min=-50.0, soft_max=200.0,
                      update=_changed)
    path: StringProperty(description="Drawn line: its points as JSON (overrides the ends)")
    by_angle: BoolProperty(name="By Angle", default=False, update=_changed,
                           description="Set the line by its start, an angle and a length "
                           "instead of its two ends")
    angle: FloatProperty(name="Angle", description="Angle from straight up the centre fold, "
                         "turning towards the left (degrees): 90 runs straight out to the "
                         "left, over 90 runs down", default=60.0, min=-180.0, max=180.0,
                         update=_changed)
    length: FloatProperty(name="Length", description="How far it runs (mm); running past "
                          "the edge of the paper is fine", default=100.0, min=1.0,
                          soft_max=500.0, update=_changed)

    group: IntProperty(description="Lines added together as one shape (a preset) share it")
    shape_name: StringProperty(name="Shape", description="The shape these lines make")
    expanded: BoolProperty(name="Show Lines", default=False, update=_line_expand,
                           description="Show the shape's lines one by one")
    pivot_x: FloatProperty()  # the shape's centre as added: Turn turns about it
    pivot_y: FloatProperty()
    flip: BoolProperty(name="Flip Across Fold", default=False, update=_line_xform,
                       description="Mirror the shape to the other side of the fold it "
                       "starts from (a box: from over the top to down the front)")
    turn: FloatProperty(name="Turn", subtype="ANGLE", default=0.0, min=-2 * math.pi,
                        max=2 * math.pi, update=_line_xform,
                        description="Turn the shape about its centre")
    move_x: FloatProperty(name="Move X", default=0.0, soft_min=-150.0, soft_max=150.0,
                          update=_line_xform, description="Move the shape across (mm)")
    move_y: FloatProperty(name="Move Y", default=0.0, soft_min=-150.0, soft_max=150.0,
                          update=_line_xform, description="Move the shape along (mm)")

    def base_points(self):
        if self.path:
            import json
            try:
                return [tuple(q) for q in json.loads(self.path)]
            except ValueError:
                pass
        if self.by_angle:
            a = math.radians(self.angle)
            return [(self.x0, self.y0), (self.x0 - self.length * math.sin(a),
                                         self.y0 + self.length * math.cos(a))]
        return [(self.x0, self.y0), (self.x1, self.y1)]

    def points(self):
        pts = self.base_points()
        if not (self.flip or self.turn or self.move_x or self.move_y):
            return pts
        if self.group:
            px, py = self.pivot_x, self.pivot_y
        else:
            px = 0.5 * (min(q[0] for q in pts) + max(q[0] for q in pts))
            py = 0.5 * (min(q[1] for q in pts) + max(q[1] for q in pts))
        if self.flip:
            pts = [(-x, y) for x, y in pts]
            px = -px
        if self.turn:
            c, s_ = math.cos(self.turn), math.sin(self.turn)
            pts = [(px + (x - px) * c - (y - py) * s_, py + (x - px) * s_ + (y - py) * c)
                   for x, y in pts]
        return [(x + self.move_x, y + self.move_y) for x, y in pts]


def _strap(self, context):
    """Strap on: both sides the same, named a strap; off: a box fold again."""
    import re
    from .ops import unique_label
    st = context.scene.popup
    if self.strap:
        self["depth"] = self.height
    base, other = ("Strap", "Box fold") if self.strap else ("Box fold", "Strap")
    if re.fullmatch(re.escape(other) + r" \d+", self.label):
        self.label = unique_label(st.mechs, base, self)
    _changed(self, context)


class PopupMech(bpy.types.PropertyGroup):
    uid: IntProperty()
    kind: EnumProperty(items=KINDS, update=_changed)
    label: StringProperty(name="Name", default="Mechanism")
    y: FloatProperty(name="Position", description="Where it sits along the fold it stands "
                     "on (mm): up the spine from the card's bottom edge; up a V-fold's crease "
                     "from its point; out along a glue line from the V point; along a box "
                     "fold, strap, cube or tube wall from its end", default=70.0, min=0.0, soft_max=300.0,
                     update=_changed)
    host_uid: IntProperty(default=0)
    host: EnumProperty(name="Host", description="Fold this mechanism sits on",
                       items=host_items, get=_host_get, set=_host_set)
    fold: EnumProperty(name="Fold", items=FOLDS, update=_fold_changed,
                       description="Which fold of the host box")
    # V-fold
    shape: EnumProperty(name="Shape", items=[
        ("QUAD", "Panels", "Each half is a four-sided panel"),
        ("TRI", "Beak", "Each half is a triangle meeting at a point: beaks and mouths"),
        ("BEAK_L", "Beak Left, Panel Right", "The left half a triangle to the crease's "
         "end, the right half a four-sided panel"),
        ("BEAK_R", "Panel Left, Beak Right", "The left half a four-sided panel, the right "
         "half a triangle to the crease's end")],
        update=_changed)
    # cube
    size: FloatProperty(name="Size", description="Width of each wall (mm)", default=40.0,
                        min=5.0, soft_max=150.0, update=_changed)
    wall: EnumProperty(name="Fold", update=lambda self, ctx: _fold_changed(self, ctx), items=[
        ("NONE", "Roof Crease", "On a tube: across its dipped flat roof's centre crease"),
        ("L", "Left Wall", "Where the host's left (front-left) wall meets the page, "
         "outside it: the wall as the background"),
        ("R", "Right Wall", "Where the host's right (front-right) wall meets the page, "
         "outside it")],
        description="On a cube or tube: which wall's foot it stands at")
    size_r: FloatProperty(name="Width Right", default=0.0, min=0.0, soft_max=150.0,
                          update=_changed,
                          description="Cube: width of the front-right (and back-left) walls "
                          "for a rectangular base, mm (0 = square). Only a square base takes "
                          "a lid")
    lid: EnumProperty(name="Lid", items=[
        ("PEAK", "Peaked", "Two-triangle lid that rises to a ridge as the card closes"),
        ("DIP", "Dipped", "Two-triangle lid that sinks into the box as the card closes"),
        ("NONE", "None", "Open top")], update=_changed)
    # flap
    side: EnumProperty(name="Page", items=[("R", "Right", ""), ("L", "Left", "")],
                       update=_changed)
    x: FloatProperty(name="From Spine", description="Distance from the spine to the "
                     "middle of the hinge (mm)", default=70.0, min=0.0, soft_max=300.0,
                     update=_changed)
    hinge: EnumProperty(name="Hinge", description="Which edge of the flap is hinged",
                        items=[("TOP", "Top", ""), ("BOTTOM", "Bottom", ""),
                               ("LEFT", "Left", ""), ("RIGHT", "Right", "")], update=_changed)
    length: FloatProperty(name="Length", description="Hinge to the free edge (mm)",
                          default=35.0, min=5.0, soft_max=200.0, update=_changed)
    angle: FloatProperty(name="Lift", description="How far the flap lifts at full pull "
                         "(degrees)", default=150.0, min=10.0, max=175.0, update=_changed)
    strip: FloatProperty(name="Strip Width", default=10.0, min=3.0, soft_max=40.0,
                         update=_changed)
    glue_at: FloatProperty(name="Glue Point", description="Where the strip is glued under "
                           "the flap, measured from the hinge (mm). Closer lifts further "
                           "for less pull", default=5.0, min=3.0, soft_max=150.0,
                           update=_changed)
    gap: FloatProperty(name="Slit Gap", description="Gap between the hinge tab and the slit "
                       "the strip comes up through (mm)", default=4.0, min=1.0, soft_max=30.0,
                       update=_changed)
    pull_out: FloatProperty(name="Pull Tab", description="How far the strip sticks out "
                            "past the card edge (mm)", default=30.0, min=5.0, soft_max=100.0,
                            update=_changed)
    # tube
    front: FloatProperty(name="Front Width", description="Width of each of the two front "
                         "walls (mm). Equal to the strip distance makes a flat front (box)",
                         default=30.0, min=2.0, soft_max=150.0, update=_changed)
    back: FloatProperty(name="Back Width", description="Width of each of the two back walls",
                        default=30.0, min=2.0, soft_max=150.0, update=_changed)
    front_style: EnumProperty(name="Front", items=[
        ("OUT", "Pointed Out", "The front crease points forward (hexagon)"),
        ("IN", "Pointed In", "The front crease points into the tube (recessed)")],
        update=_changed)
    back_style: EnumProperty(name="Back", items=[
        ("OUT", "Pointed Out", "The back crease points backward (hexagon)"),
        ("IN", "Pointed In", "The back crease points into the tube")], update=_changed)
    roof: EnumProperty(name="Roof", items=[
        ("NONE", "None", "Open top"),
        ("POINTED", "Pointed", "Pyramid or ridge roof (set Roof Height and Ridge)"),
        ("FLAT", "Flat", "Flat roof creased down the middle above the fold, optionally "
         "overhanging the walls")], update=_changed)
    roof_fold: EnumProperty(name="Fold", items=[
        ("PEAK", "Peak", "The centre crease rises as the card closes"),
        ("DIP", "Dip", "The centre crease sinks into the tube as the card closes (needs "
         "walls at least as tall as the strip distance)")], update=_changed)
    rib: FloatProperty(name="Centre Rib", description="Length of the rib holding a dipped "
                       "roof up from the spine (mm); 0 for none", default=20.0, min=0.0,
                       soft_max=150.0, update=_changed)
    lead: FloatProperty(name="Point", description="How far a floor's or ceiling's centre "
                        "runs on past the front of the stage (mm). It is shortened if it "
                        "would stick out when shut", default=0.0, min=0.0, soft_max=200.0,
                        update=_changed)
    eave: FloatProperty(name="Overhang", description="How far a flat roof reaches past the "
                        "walls all round (mm)", default=0.0, min=0.0, soft_max=40.0,
                        update=_changed)
    roof_height: FloatProperty(name="Roof Height", description="How far the roof rises "
                               "above the walls, card open flat (mm)", default=30.0, min=1.0,
                               soft_max=150.0, update=_changed)
    ridge: FloatProperty(name="Ridge", description="Length of the ridge along the fold (mm). "
                         "0 makes a pyramid; the full length makes a tent with upright ends",
                         default=0.0, min=0.0, soft_max=200.0, update=_changed)
    # tether
    from_uid: IntProperty()
    from_tube: EnumProperty(name="From", items=tube_items, get=_get_from, set=_set_from)
    from_pt: EnumProperty(name="Point", items=POINTS, update=_changed)
    to: EnumProperty(name="To", items=[
        ("LEFT", "Left Strip", "A foot glued on the left strip"),
        ("RIGHT", "Right Strip", "A foot glued on the right strip"),
        ("TUBE", "Another Tube", "A point on another tube")], update=_changed)
    to_uid: IntProperty()
    to_tube: EnumProperty(name="Tube", items=tube_items, get=_get_to, set=_set_to)
    to_pt: EnumProperty(name="Point", items=POINTS, default="FR", update=_changed)
    to_y: FloatProperty(name="Foot Position", description="Distance of the foot up the strip "
                        "from the bottom edge (mm)", default=60.0, min=0.0, soft_max=300.0,
                        update=_changed)
    slack: FloatProperty(name="Slack", description="Extra length so a creased tether never "
                         "pulls tight (mm)", default=0.0, min=0.0, soft_max=30.0,
                         update=_changed)
    bend: EnumProperty(name="Bend", items=[
        ("AUTO", "Auto", "The side that keeps the crease between the strips"),
        ("FRONT", "Front", "Crease bends towards the front"),
        ("BACK", "Back", "Crease bends towards the back")], update=_changed)
    # mouth
    jaw: FloatProperty(name="Jaw Length", description="How far the slit runs from the "
                       "fold on each side (mm)", default=30.0, min=2.0, soft_max=150.0,
                       update=_changed)
    upper: FloatProperty(name="Upper Jaw", description="Fold height of the upper jaw "
                         "above the slit (mm)", default=20.0, min=1.0, soft_max=150.0,
                         update=_changed)
    lower: FloatProperty(name="Lower Jaw", description="Fold height of the lower jaw "
                         "below the slit (mm)", default=15.0, min=1.0, soft_max=150.0,
                         update=_changed)
    symmetric: BoolProperty(name="Symmetric", default=True, update=_sym)
    fold_flat: BoolProperty(name="Fold Flat", default=True, update=_changed,
                            description="Asymmetric V-fold: work out the piece angles from "
                            "the glue angles and the Lean, so the piece always folds flat "
                            "in the closed card (left piece angle = right glue angle + Lean, "
                            "right piece angle = left glue angle + Lean; glue angles over 90 "
                            "point it backwards and are measured from the other end of the "
                            "spine). Off: set them yourself")
    lean: FloatProperty(name="Lean", description="How much each piece angle is bigger than "
                        "the opposite glue angle (degrees). The centre crease leans towards "
                        "the side with the bigger glue angle; more Lean, steeper planes",
                        default=20.0, min=1.0, max=90.0, update=_changed)
    phi_l: FloatProperty(name="Glue Angle L", description="Angle between the spine and "
                         "the left glue line (degrees)", default=60.0, min=5.0,
                         max=175.0, update=_sym)
    phi_r: FloatProperty(name="Glue Angle R", default=60.0, min=5.0, max=175.0,
                         update=_changed)
    alpha_l: FloatProperty(name="Piece Angle L", description="Angle between the piece's "
                           "centre fold and its left glue edge (degrees). Must be at "
                           "least the glue angle or the paper tears before the card "
                           "is flat", default=80.0, min=5.0, max=175.0, update=_sym)
    alpha_r: FloatProperty(name="Piece Angle R", default=80.0, min=5.0, max=175.0,
                           update=_changed)
    glue: FloatProperty(name="Glue Length", description="Length of each glue edge (mm)",
                        default=40.0, min=2.0, soft_max=150.0, update=_changed)
    peaks: IntProperty(name="Peaks", default=1, min=1, max=8, update=_changed,
                       description="Box fold or strap: creases along the strip so it "
                       "zig-zags into this many peaks as the card closes (still glued only "
                       "at its ends). Each valley between two peaks opens like a small spine "
                       "and can carry a pop-up (Fold: Valley)")
    gully: IntProperty(name="Gully", default=1, min=1, max=5, update=lambda s, c: _fold_changed(s, c),
                       description="Which valley of a strap with several peaks, counted from "
                       "the left")
    strap: BoolProperty(name="Strap (lies flat)", default=False, update=lambda s, c: _strap(s, c),
                        description="Equal sides, so it lies flat on the pages when the card "
                        "is open: its two glue folds become gullies off the centre that "
                        "open just like the spine, for pop-ups away from it (Tutorial 9)")
    pleat: FloatProperty(name="Concertina", default=0.0, min=0.0, max=170.0,
                         update=_changed,
                         description="For extra creases that leave the paper free to fold "
                         "more than one way (a fan, a concertina): how far they fold when "
                         "the card is shut (degrees), alternating mountain and valley, as if "
                         "pre-folded. They open out flat with the card. 0: they fold only as "
                         "far as they must")
    slant: FloatProperty(name="Slant", default=0.0, min=-60.0, max=60.0, precision=1,
                         update=_changed,
                         description="Box fold or strap: run the strip across the fold at "
                         "an angle (degrees from square). Its creases stay parallel to the "
                         "fold; one end sits further up the card than the other, so what "
                         "stands on its folds is offset diagonally")
    glue_r: FloatProperty(name="Glue Length R", default=0.0, min=0.0, soft_max=150.0,
                          update=_changed,
                          description="Asymmetric V-fold: length of the right glue edge "
                          "(mm; 0 = as the left)")
    tab_side: EnumProperty(name="Tab Side", items=[
        ("IN", "Inside", "Tabs fold in, under the piece"),
        ("OUT", "Outside", "Tabs fold out, away from the piece")], update=_changed)
    # shared
    height: FloatProperty(name="Height", description="V-fold: length of the centre fold. "
                          "Box: distance up the left page (mm)", default=50.0, min=2.0,
                          soft_max=150.0, update=_changed)
    depth: FloatProperty(name="Depth", description="Distance across the right page (mm)",
                         default=30.0, min=2.0, soft_max=150.0, update=_changed)
    width: FloatProperty(name="Width", description="Width along the spine (mm)",
                         default=50.0, min=2.0, soft_max=200.0, update=_changed)
    tab: FloatProperty(name="Tab Size", description="Glue tab size (mm)", default=12.0,
                       min=3.0, soft_max=30.0, update=_changed)
    vside: EnumProperty(name="Fold", description="Which half of the host V-fold, and "
                        "which side of it", items=[
                            ("FL", "In Front, Left", "Stands on the page in front of the "
                             "left half, the half as its background"),
                            ("BL", "Behind, Left", "Inside the V, against the back of the "
                             "left half"),
                            ("FR", "In Front, Right", "Stands on the page in front of the "
                             "right half"),
                            ("BR", "Behind, Right", "Inside the V, against the back of the "
                             "right half"),
                            ("V", "On the Crease", "Across the V-fold's own centre crease, "
                             "between its halves: the V-fold is its spine")],
                        update=_fold_changed)
    cut_above: BoolProperty(name="Cut Away Background Above", default=False,
                            update=_changed,
                            description="A V-fold on the card's spine whose glue lines fall "
                            "away from it (Glue Angle over 90) as a roof or ceiling: cut the "
                            "background away above its glue lines, so only the V-fold shows "
                            "above them")
    valley: BoolProperty(name="Upside Down (Valley Floor)", default=False,
                         update=_changed,
                         description="The roof turned upside down: the background is cut "
                         "away below two lines rising from the spine and a V-fold floor is "
                         "glued along them, dipping to a valley")
    level: BoolProperty(name="Level Ridge", default=True, update=_changed,
                        description="Work out the roof's piece angle so its ridge runs "
                        "level when the card (or stage) is fully open. Off: set the Piece "
                        "Angle yourself (bigger tilts the ridge up)")
    on_crease: BoolProperty(name="On the Crease", default=False, update=_changed,
                            description="Stand on the floor's (ceiling's) centre crease "
                            "instead of in a corner. Only V-folds can: from the stage side "
                            "the crease is a mountain fold")
    # stand-up
    stand: EnumProperty(name="Picture", items=[
        ("UPRIGHT", "Upright", "The picture stands parallel to the background, held by a "
         "bridge from the background to its back"),
        ("FLAT", "Flat", "The picture lies parallel to the floor (a flying carpet), glued to "
         "the background and held up by a leg")], update=_changed)
    img_w: FloatProperty(name="Picture Width", description="Width of the picture along "
                         "the fold (mm), centred on its bridge or leg", default=80.0,
                         min=2.0, soft_max=250.0, update=_changed)
    img_h: FloatProperty(name="Picture Height", description="Upright: height of the "
                         "picture from the floor. Flat: how far it reaches out from the "
                         "background (mm)", default=90.0, min=2.0, soft_max=250.0,
                         update=_changed)
    lines: CollectionProperty(type=PopupLine)
    active_line: IntProperty(name="Line")

    def to_dict(self):
        d = dict(uid=self.uid, label=self.label, y=self.y, tab=self.tab,
                 host=self.host_uid, fold=self.fold, side=self.side, wall=self.wall,
                 gully=self.gully,
                 vside="V" if self.on_crease else self.vside)
        if self.kind == "TUBE":
            d.update(type="TUBE", x=self.x, depth=self.depth, height=self.height,
                     front=self.front, back=self.back, front_style=self.front_style,
                     back_style=self.back_style, tab_side=self.tab_side, roof=self.roof,
                     roof_height=self.roof_height, ridge=self.ridge,
                     roof_fold=self.roof_fold, eave=self.eave, rib=self.rib)
        elif self.kind == "ROOF":
            d.update(type="ROOF", phi_l=self.phi_l, alpha_l=self.alpha_l, glue=self.glue,
                     height=self.height, level=self.level, tab_side=self.tab_side,
                     valley=self.valley,
                     pleat=self.pleat,
                     lines=[dict(kind=ln.kind, mirror=ln.mirror, pts=ln.points())
                            for ln in self.lines])
        elif self.kind == "STANDUP":
            d.update(type="STANDUP", stand=self.stand, width=self.width, height=self.height,
                     depth=self.depth, img_w=self.img_w, img_h=self.img_h)
        elif self.kind == "STAGE":
            d.update(type="STAGE", phi_l=self.phi_l, glue=self.glue, height=self.height,
                     tab_side=self.tab_side)
        elif self.kind == "FRAME":
            d.update(type="FRAME", x=self.x, height=self.height)
        elif self.kind in ("FLOOR", "CEILING"):
            d.update(type=self.kind, depth=self.depth, lead=self.lead)
        elif self.kind == "PYRAMID":
            d.update(type="PYRAMID", x=self.x, depth=self.depth, height=self.height,
                     ridge=self.ridge, front=self.front, back=self.back,
                     front_style=self.front_style, back_style=self.back_style,
                     tab_side=self.tab_side)
        elif self.kind == "TETHER":
            d.update(type="TETHER", from_uid=self.from_uid, from_pt=self.from_pt, to=self.to,
                     to_uid=self.to_uid, to_pt=self.to_pt, to_y=self.to_y, slack=self.slack,
                     bend=self.bend, height=self.height, tab_side=self.tab_side)
        elif self.kind == "CUBE":
            d.update(type="CUBE", size=self.size, height=self.height, lid=self.lid,
                     size_r=self.size_r,
                     tab_side=self.tab_side)
        elif self.kind == "FLAP":
            d.update(type="FLAP", side=self.side, x=self.x, hinge=self.hinge,
                     width=self.width, length=self.length, angle=self.angle,
                     strip=self.strip, glue_at=self.glue_at, gap=self.gap,
                     pull_out=self.pull_out)
        elif self.kind == "MOUTH":
            d.update(type="MOUTH", jaw=self.jaw, upper=self.upper, lower=self.lower)
        elif self.kind == "VFOLD":
            al, ar = self.alpha_l, self.alpha_r
            if self.symmetric:
                ar = al
            elif self.fold_flat:
                if self.phi_l + self.phi_r > 180.0:  # pointing backwards (Birmingham 31)
                    al, ar = 180.0 - self.phi_r + self.lean, 180.0 - self.phi_l + self.lean
                else:
                    al, ar = self.phi_r + self.lean, self.phi_l + self.lean
            d.update(type="VFOLD", phi_l=self.phi_l, alpha_l=al,
                     phi_r=self.phi_l if self.symmetric else self.phi_r, alpha_r=ar,
                     glue=self.glue, height=self.height, tab_side=self.tab_side,
                     glue_r=self.glue if self.symmetric or self.glue_r <= 0 else self.glue_r,
                     shape=self.shape, cut_above=self.cut_above,
                     pleat=self.pleat,
                     lines=[dict(kind=ln.kind, mirror=ln.mirror, pts=ln.points())
                            for ln in self.lines])
        else:
            d.update(type="BOX", style="CUT" if self.kind == "BOXCUT" else "GLUED",
                     width=self.width, height=self.height,
                     depth=self.height if (self.strap and self.kind == "BOX") else self.depth,
                     slant=self.slant, peaks=self.peaks if self.kind == "BOX" else 1,
                     pleat=self.pleat,
                     lines=[dict(kind=ln.kind, mirror=ln.mirror, pts=ln.points())
                            for ln in self.lines])
        return d


def _sizes():
    from .core.model import CARD_PRESETS
    items = [(k, v[3], v[4]) for k, v in CARD_PRESETS.items()]
    return items + [("CUSTOM", "Custom", "Set page width and spine length")]


SIZES = _sizes()

PAPERS = {
    "A4L": ((297.0, 210.0), "A4 landscape"),
    "A4P": ((210.0, 297.0), "A4 portrait"),
    "A3L": ((420.0, 297.0), "A3 landscape"),
    "LETTER": ((279.4, 215.9), "US Letter landscape"),
    "TABLOID": ((431.8, 279.4), "Tabloid 11 x 17 in landscape"),
    "MAT12": ((304.8, 304.8), "Cutting mat 12 x 12 in"),
    "MAT24": ((609.6, 304.8), "Cutting mat 12 x 24 in"),
}


_on_items = []


def on_items(self, context):
    """Every piece of paper the opening can be cut in: the card (a stage's
    background) or any mechanism's piece, roofs, ribs and strips included."""
    global _on_items
    st = context.scene.popup if context and context.scene else None
    meta = live.meta(st.rig) if st is not None else None
    items = []
    if meta:
        for name, info in sorted(meta["pieces"].items(), key=lambda kv: kv[1]["slot"]):
            label = ("Background" if st.stage_master else "Card") if info["is_card"] \
                else info["label"]
            items.append((name, label, "", "FILE_BLANK" if info["is_card"] else "OBJECT_DATA",
                          int(info["slot"])))
    if not items:
        items = [("Card", "Card", "", "FILE_BLANK", 0)]
    _on_items = items
    return _on_items


def _opening_changed(self, context):
    scene = context.scene
    live.schedule(scene)
    if self.through == "NEXT" or self.get("_was_next"):
        from . import holes
        for other in holes._neighbours(scene):
            if other is not None and other != scene:
                live.schedule(other)
    self["_was_next"] = self.through == "NEXT"


def _on_get(self):
    st = bpy.context.scene.popup
    meta = live.meta(st.rig)
    if meta and self.on_piece in meta["pieces"]:
        return int(meta["pieces"][self.on_piece]["slot"])
    return 0 if not self.on_uid else 1 + self.on_uid


def _on_set(self, v):
    st = bpy.context.scene.popup
    meta = live.meta(st.rig)
    if meta:
        for name, info in meta["pieces"].items():
            if int(info["slot"]) == v:
                if name != self.on_piece:
                    self.face = ""
                self.on_piece = name
                break
    live.schedule(bpy.context.scene)


_face_items = []


def face_items(self, context):
    """The faces of the piece an opening is cut in (folded panels: a box's
    top and front, a cube's walls, a page)."""
    global _face_items
    st = context.scene.popup if context and context.scene else None
    meta = live.meta(st.rig) if st is not None else None
    items = [("WHOLE", "Whole Piece", "X and Y on the whole piece's pattern", "FILE_BLANK", 0)]
    if meta:
        piece = self.on_piece or "Card"
        for i, p in enumerate(meta["panels"]):
            if p["piece"] == piece and p["kind"] != "tab":
                label = p["label"].split(": ", 1)[-1]
                if piece == "Card" and ": " in p["label"]:
                    label = p["label"]  # a box layer's faces, cut in the card
                items.append((p["name"], label[:1].upper() + label[1:], "", "MESH_PLANE",
                              i + 1))
    _face_items = items
    return _face_items


def _face_get(self):
    for it in face_items(self, bpy.context):
        if it[0] == (self.face or "WHOLE"):
            return it[4]
    return 0


def _face_set(self, v):
    for it in face_items(self, bpy.context):
        if it[4] == v:
            self.face = "" if it[0] == "WHOLE" else it[0]
            break
    live.schedule(bpy.context.scene)


class PopupOpening(bpy.types.PropertyGroup):
    label: StringProperty(name="Name", default="Opening")
    on_uid: IntProperty()  # older files: the mechanism (0 = card)
    on_piece: StringProperty(description="The piece the opening is cut in")
    on: EnumProperty(name="Cut In", items=on_items, get=_on_get, set=_on_set,
                     description="The piece the opening is cut in")
    face: StringProperty(description="The face (panel) the opening is placed on")
    face_pick: EnumProperty(name="Face", items=face_items, get=_face_get, set=_face_set,
                            description="Place it on one face of the piece: X across "
                            "the face from its centre, Y up from its bottom edge, and "
                            "kept inside the face so it never cuts through a fold")
    turn: FloatProperty(name="Turn", subtype="ANGLE", default=0.0, min=-math.pi * 2,
                        max=math.pi * 2, update=_opening_changed,
                        description="Turns the opening about its centre")
    cut: EnumProperty(name="Cut", items=[
        ("HOLE", "Hole", "Cut right out: a window or an open doorway"),
        ("DOOR", "Door Flap", "Cut on every side but one, which is creased as a hinge: "
         "the door swings open as the card opens (on the card, V-folds, box folds and "
         "box layers)")], update=_opening_changed)
    hinge: EnumProperty(name="Hinge", items=[
        ("LEFT", "Left", "Hinged down its left side"),
        ("RIGHT", "Right", "Hinged down its right side"),
        ("BOTTOM", "Bottom", "Hinged along its bottom: it folds down like a drawbridge (on "
         "a box's front, a door hinged on the floor fold stays flat on the floor)"),
        ("TOP", "Top", "Hinged along its top, like a cat flap (rectangles)")],
        default="LEFT", update=_opening_changed)
    door_open: FloatProperty(name="Opens To", default=60.0, min=0.0, max=170.0,
                             update=_opening_changed,
                             description="How far the door swings out when the card is fully "
                             "open (degrees); it closes flat as the card shuts")
    shape: EnumProperty(name="Shape", items=[
        ("RECT", "Rectangle", "Window or plain doorway"),
        ("ARCH", "Arch", "Round-topped doorway or window"),
        ("OVAL", "Oval", "Round or oval window")], update=_opening_changed)
    x: FloatProperty(name="X (Across Page)", description="Where its centre is, across the "
                     "page from the centre fold (mm; the left page is negative)", default=0.0,
                     soft_min=-300.0, soft_max=300.0, update=_opening_changed)
    y: FloatProperty(name="Y (Up Page)", description="Where its bottom edge is, up the "
                     "page from the bottom edge (mm)", default=20.0, soft_min=0.0, soft_max=300.0,
                     update=_opening_changed)
    width: FloatProperty(name="Width", default=30.0, min=1.0, soft_max=300.0,
                         update=_opening_changed)
    height: FloatProperty(name="Height", default=40.0, min=1.0, soft_max=300.0,
                          update=_opening_changed)
    through: EnumProperty(name="Through", items=[
        ("NONE", "This Piece", "Cut in this piece only"),
        ("BEHIND", "Everything Behind", "Also cut in every frame behind it and the "
         "background, lined up as seen from the front when the stage is fully open"),
        ("NEXT", "Next Stage", "On a background page: also cut in the neighbouring "
         "stage's page glued back to back with it (a doorway between stages)")],
        update=_opening_changed)


class PopupStageRef(bpy.types.PropertyGroup):
    scene: PointerProperty(type=bpy.types.Scene)


def _carousel_changed(self, context):
    from . import carousel
    carousel.schedule_sync(self.id_data)


def _look(self, context):
    from . import scene_setup
    sc = self.id_data
    scene_setup.render_look(scene_setup.popup_scenes(sc), self.render_look)


def _clean(self, context):
    from . import scene_setup
    sc = self.id_data
    scene_setup.clean_render(scene_setup.popup_scenes(sc), self.clean_render)


def _ceiling_style(self, context):
    # each style's natural starting slope
    self.ceiling_slope = {"HANG": 30.0, "PEAK": -10.0}.get(self.ceiling, self.ceiling_slope)
    _changed(self, context)


def _floor_style(self, context):
    self.floor_slope = {"HANG": 30.0, "PEAK": -10.0}.get(self.floor, self.floor_slope)
    _changed(self, context)


class PopupSettings(bpy.types.PropertyGroup):
    size: EnumProperty(name="Card", items=SIZES, default="A5", update=_changed)
    page_depth: FloatProperty(name="Page Width", description="Spine to page edge (mm)",
                              default=148.5, min=20.0, soft_max=400.0, update=_changed)
    spine_length: FloatProperty(name="Spine Length", default=210.0, min=20.0,
                                soft_max=400.0, update=_changed)
    hold: EnumProperty(name="Opens", description="How the card opens: like a picture "
                       "book, both pages turning out from the spine, or one page flat on "
                       "the table while the other turns over", items=[
                           ("RIGHT", "Right Page Flat", "The right page lies on the table; "
                            "the left turns over to the left"),
                           ("LEFT", "Left Page Flat", "The left page lies on the table; "
                            "the right turns over to the right"),
                           ("SYM", "Picture Book", "Both pages open out symmetrically "
                            "from the spine")],
                       default="SYM", update=_changed)
    paper: EnumProperty(name="Piece Paper", items=[(k, v[1], "") for k, v in PAPERS.items()],
                        description="Sheet size for the loose pieces", update=_changed)
    mm_per_unit: FloatProperty(name="mm per Unit", description="Millimetres of paper per "
                               "Blender unit (10 = 1 unit is 1 cm)", default=10.0,
                               min=0.01, soft_max=1000.0, update=_changed)
    mechs: CollectionProperty(type=PopupMech)
    active: IntProperty(name="Mechanism", update=_redraw)
    highlight: BoolProperty(name="Highlight Selected", default=True, update=_redraw,
                            description="Tint the panels of the mechanism selected in the "
                            "list, on the folded card and the layout (viewport only, never "
                            "rendered; off while painting)")
    live: BoolProperty(name="Live Rebuild", description="Rebuild the card as you change "
                       "settings", default=True)
    rig: PointerProperty(type=bpy.types.Object, name="Rig")
    card: PointerProperty(type=bpy.types.Object, name="Card")
    layout: PointerProperty(type=bpy.types.Object, name="Layout")
    warnings: StringProperty()
    status: StringProperty()
    edited: BoolProperty(description="The card mesh has been edited by hand")
    sketch_panel: EnumProperty(name="Panel", items=lambda s, c: live.panel_items(c.scene))
    # export ------------------------------------------------------------
    export_content: EnumProperty(name="Content", items=[
        ("PRINT", "Print", "Artwork, tabs, glue guides and all lines"),
        ("ART_CUT", "Art + Cut Lines", "Artwork outlined by cut lines only: no fold lines "
         "or guides over the art; file name ends _art"),
        ("CUT", "Cut Lines Only", "Only the lines to cut (cutting machine cut layer)"),
        ("CREASE", "Crease Lines Only", "Only the folds (cutting machine score layer)"),
        ("LINES", "Cut + Crease", "All lines in one file, creases red so they import as "
         "their own colour layer; no artwork")],
        description="What goes in the SVG. For a Cricut, export Cut and Crease as "
        "separate files and set them to Cut and Score in Design Space")
    line_style: EnumProperty(name="Lines", items=[
        ("DEFAULT", "Default", "Black cuts, red mountain folds, blue valley folds"),
        ("CUSTOM", "Custom Colour", "All lines in one colour and opacity, e.g. white "
         "over dark art or soft black over light art"),
        ("NONE", "No Lines", "Print the art only (lines stay in the file as hidden "
         "layers)")], default="DEFAULT")
    line_color: FloatVectorProperty(name="Line Colour", subtype="COLOR", size=3, min=0.0,
                                    max=1.0, default=(0.0, 0.0, 0.0))
    line_opacity: FloatProperty(name="Line Opacity", default=0.35, min=0.0, max=1.0,
                                subtype="FACTOR")
    line_width: FloatProperty(name="Line Width", description="Stroke width (mm)",
                              default=0.3, min=0.05, max=2.0)
    dashed_folds: BoolProperty(name="Dashed Folds", default=True,
                               description="Dash fold lines. Turn off for cutting "
                               "machines, which score a dashed line as many short "
                               "pieces")
    tab_fill: BoolProperty(name="Colour Tabs", default=False,
                           description="Fill plain glue tabs with a colour. Off: tabs stay "
                           "paper white, outlined by their cut lines")
    tab_color: FloatVectorProperty(name="Tab Colour", subtype="COLOR", size=3, min=0.0,
                                   max=1.0, default=(0.85, 0.83, 0.78))
    bleed: FloatProperty(name="Bleed", default=0.0, min=0.0, max=3.0, precision=2,
                         description="Millimetres of art printed past each piece's "
                         "outline, so slightly-off cuts don't show white (0 = off)")
    export_art: BoolProperty(name="Artwork", default=True)
    export_sketch: BoolProperty(name="Sketches", default=True)
    export_guides: BoolProperty(name="Glue Guides", default=True)
    export_labels: BoolProperty(name="Labels", default=True)
    true_colours: BoolProperty(name="True Colours While Painting", default=True,
                               description="In Texture Paint, show the paper unlit with the "
                               "Standard view transform, so the colours you see and pick up "
                               "with the eyedropper are the ones in the art (and in print). "
                               "Your view settings come back when you leave Texture Paint")
    # the background itself folding in: set by a few numbers ---------------
    ceiling: EnumProperty(
        name="Ceiling", update=_ceiling_style, items=[
            ("NONE", "None", "The background stays flat"),
            ("HANG", "Hanging", "Two creases rising from the spine to the top edge: the "
             "top of the background folds in over the stage and hangs down in a V"),
            ("PEAK", "Peaked Roof", "The top is cut apart at the spine and joined again by "
             "a glue tab: it folds in over the stage as a peaked roof")])
    ceiling_drop: FloatProperty(name="Drop at Spine", default=40.0, min=2.0, soft_max=150.0,
                                precision=1, update=_changed,
                                description="How far below the top edge the creases meet "
                                "the spine, in mm")
    ceiling_slope: FloatProperty(name="Crease Slope", default=30.0, min=-40.0, max=80.0,
                                 precision=1, update=_changed,
                                 description="Degrees the creases climb (+) or fall (-) going "
                                 "out from the spine. A peaked roof's eaves want about -10")
    ceiling_lift: FloatProperty(name="Ridge Lift", default=0.0, min=0.0, max=40.0,
                                precision=1, update=_changed,
                                description="0: the join tab is set so the roof's ridge runs "
                                "level into the stage when it is fully open. More lifts the "
                                "ridge's front (tipping it down past level would tear)")
    floor: EnumProperty(
        name="Floor", update=_floor_style, items=[
            ("NONE", "None", "The background stays flat"),
            ("HANG", "V Floor", "Two creases falling from the spine to the bottom edge: the "
             "bottom of the background folds in as a floor, rising to a V at the centre"),
            ("PEAK", "Valley Floor", "The Peaked Roof upside down: the bottom is cut apart "
             "at the spine and joined again by a glue tab, so the floor dips to a valley")])
    floor_rise: FloatProperty(name="Rise at Spine", default=40.0, min=2.0, soft_max=150.0,
                              precision=1, update=_changed,
                              description="How far above the bottom edge the creases meet "
                              "the spine, in mm")
    floor_slope: FloatProperty(name="Crease Slope", default=30.0, min=-40.0, max=80.0,
                               precision=1, update=_changed,
                               description="Degrees the creases fall (+) or climb (-) going "
                               "out from the spine. A valley floor's edges want about -10")
    floor_dip: FloatProperty(name="Valley Dip", default=0.0, min=0.0, max=40.0,
                             precision=1, update=_changed,
                             description="0: the join tab is set so the floor's valley runs "
                             "level into the stage when it is fully open. More dips the "
                             "valley's front (tipping it up past level would tear)")
    images: CollectionProperty(type=PopupImage,
                               description="Images placed on pieces, front or back")
    active_image: IntProperty(name="Image")
    render_look: EnumProperty(name="Render Look", update=lambda self, ctx: _look(self, ctx),
                              items=[("CLEAN", "Clean", "Even white light, no sun"),
                                     ("SHOWCASE", "Showcase", "White light and the sun's "
                                      "shadows, 64 render samples"),
                                     ("DAWN", "Dawn", "Blender's sunrise light (warm sun, "
                                      "blue sky) and the sun's shadows, 64 render samples"),
                                     ("OWN", "Your Own", "Your own world and lights")],
                              description="How finished renders are lit (painting, baking and "
                              "printing never use the lighting)")
    clean_render: BoolProperty(name="Clean White Renders", default=True,
                               update=lambda self, ctx: _clean(self, ctx),
                               description="Renders lit evenly in white light, without the "
                               "viewport's sun and shadows (painting and printing never use "
                               "the lighting)")
    card_lines: CollectionProperty(type=PopupLine,
                                   description="Extra creases and cuts in the card itself")
    active_card_line: IntProperty(name="Card Line")
    auto_holes: BoolProperty(name="Cut Automatically", default=False,
                             description="Cut whatever is painted see-through (Erase) out of "
                             "the paper by itself, each time painting stops and before every "
                             "export. Off: only when you press Cut Painted Holes")
    export_reverse: BoolProperty(name="Reverse Sides", default=True,
                                 description="For pieces with tabs glued to their back, a "
                                 "mirrored sheet of glue markers to print on the other side")
    export_layout: BoolProperty(name="Assembly Page", default=True,
                                description="A page showing where each part glues on the card, "
                                "with a parts list")
    # paper --------------------------------------------------------------
    paper_thickness: FloatProperty(name="Paper Thickness", default=0.3, min=0.05, max=3.0,
                                   precision=2, update=_changed,
                                   description="Card thickness in mm (0.3 is typical card "
                                   "stock). Used to keep the closed card from crushing its "
                                   "mechanisms, and for Solid Paper")
    keep_open: BoolProperty(name="Stop at Paper Thickness", default=True, update=_changed,
                            description="Closed (Open = 0) stops where the pages meet the "
                            "folded mechanisms, instead of squashing everything flat "
                            "through itself. Off: closed is exactly 0 degrees")
    solid_paper: BoolProperty(name="Solid Paper", default=True, update=_changed,
                              description="Give the paper real thickness in the viewport and "
                              "renders (Solidify, behind the printed side)")
    anim_frames: IntProperty(name="Frames", description="(old) Frames to open",
                             default=48, min=2)
    anim_to: FloatProperty(name="Open To", description="How far the movement test opens "
                           "the card (degrees)", default=180.0, min=1.0, max=180.0)
    anim_to_carousel: FloatProperty(name="Open To", description="How far the movement test "
                                    "opens the carousel (degrees)", default=360.0, min=1.0,
                                    max=360.0)
    anim_open: FloatProperty(name="Opening", description="Seconds to open", default=2.0,
                             min=0.05, soft_max=20.0, unit="TIME_ABSOLUTE")
    anim_hold: FloatProperty(name="Hold Open", description="Seconds it stays open before "
                             "closing", default=1.0, min=0.0, soft_max=20.0,
                             unit="TIME_ABSOLUTE")
    anim_close: FloatProperty(name="Closing", description="Seconds to close", default=2.0,
                              min=0.05, soft_max=20.0, unit="TIME_ABSOLUTE")
    # carousel ---------------------------------------------------------------
    suffix: StringProperty(description="Added to this scene's data names (stages)")
    stage_master: PointerProperty(type=bpy.types.Scene, name="Carousel",
                                  description="The carousel this stage belongs to")
    stage_index: IntProperty()
    is_carousel: BoolProperty(description="This scene shows a carousel of stages")
    stage_count: IntProperty(name="Stages", description="Stages round the carousel; each "
                             "opens to 360 / Stages degrees", default=5, min=2, max=9,
                             update=_carousel_changed)
    join: EnumProperty(name="Joins", items=[
        ("GLUED", "Glued", "Each stage is its own folded card; neighbouring pages are glued "
         "back to back"),
        ("SHARED", "Shared Page", "Neighbouring stages share one sheet, printed on both "
         "sides")], update=_carousel_changed,
        description="How each stage's page joins the next stage's")
    stages: CollectionProperty(type=PopupStageRef)
    openings: CollectionProperty(type=PopupOpening)
    active_opening: IntProperty()
    carousel_ctrl: PointerProperty(type=bpy.types.Object)

    def card_dict(self):
        from .core.model import CARD_PRESETS
        master = self.stage_master
        lines = [dict(kind=ln.kind, mirror=ln.mirror, pts=ln.points())
                 for ln in self.card_lines]
        if master is not None and master != self.id_data:
            d = master.popup.card_dict()
            d.update(hold="SYM", tmax=360.0 / master.popup.stage_count,
                     piece_sheet=PAPERS[self.paper][0])
            d["lines"] = self.shape_lines(d["W"], d["H"], d["tmax"]) + lines
            d["doors"] = self.doors()
            return d
        if self.size == "CUSTOM":
            W, H = self.page_depth, self.spine_length
            sheet = (2 * W, H)
        else:
            W, H, sheet, _, _ = CARD_PRESETS[self.size]
        tmax = 180.0
        return dict(W=W, H=H, hold=self.hold, sheet=sheet,
                    piece_sheet=PAPERS[self.paper][0],
                    thickness=self.paper_thickness if self.solid_paper else 0.0,
                    lines=self.shape_lines(W, H, tmax) + lines, doors=self.doors())

    def doors(self):
        from .core.openings import opening_dict
        return [opening_dict(o, i) for i, o in enumerate(self.openings) if o.cut == "DOOR"]

    def shape_lines(self, W, H, tmax):
        """The creases (and cut) the Ceiling and Floor settings make."""
        return card_shape_lines(W, H, tmax, self.ceiling, self.ceiling_drop,
                                self.ceiling_slope, self.ceiling_lift,
                                self.floor, self.floor_rise, self.floor_slope, self.floor_dip)


def card_shape_lines(W, H, tmax, ceiling="NONE", drop=40.0, slope=30.0, lift=0.0,
                     floor="NONE", rise=40.0, fslope=30.0, dip=0.0):
    """The lines the Ceiling and Floor settings make. A floor is its ceiling
    turned upside down (the card folds the same either way up)."""
    if floor is True:
        floor = "HANG"
    elif floor is False:
        floor = "NONE"
    L = 2.0 * max(W, H) + 20.0

    def shape(style, d, sl, tl, flip):
        if style == "NONE":
            return []
        y0 = max(1.0, min(H - 1.0, H - d))
        ang = 90.0 - sl  # from straight up the spine, out over the left page

        def ray(kind, a):
            a = math.radians(a)
            return [(0.0, y0), (-L * math.sin(a), y0 + L * math.cos(a))]

        out = [("CREASE", True, ray("CREASE", ang))]
        if style == "PEAK":
            # the join tab that runs the ridge level at the stage's full
            # opening (fitted to the solved shape: within a degree or two)
            psi = ang - 1.0 - 0.5 * min(tmax, 180.0) - 0.15 * max(0.0, ang - 100.0)
            psi = max(3.0, min(ang - 3.0, psi - max(0.0, tl)))
            out.append(("JOIN", True, ray("JOIN", psi)))
            out.append(("CUT", False, [(0.0, y0), (0.0, H + 5.0)]))
        res = []
        for kind, mir, pts in out:
            if flip:
                pts = [(x, H - y) for x, y in pts]
            res.append(dict(kind=kind, mirror=mir, pts=pts))
        return res

    return shape(ceiling, drop, slope, lift, False) + shape(floor, rise, fslope, dip, True)


classes = (PopupImage, PopupLine, PopupMech, PopupOpening, PopupStageRef, PopupSettings)


def register():
    for c in classes:
        bpy.utils.register_class(c)
    bpy.types.Scene.popup = PointerProperty(type=PopupSettings)


def unregister():
    del bpy.types.Scene.popup
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
