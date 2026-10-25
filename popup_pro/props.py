import bpy
from bpy.props import (BoolProperty, CollectionProperty, EnumProperty,
                       FloatProperty, FloatVectorProperty, IntProperty, PointerProperty,
                       StringProperty)

from . import live


def _changed(self, context):
    live.schedule(context.scene)


def _sym(self, context):
    if self.symmetric:
        self["phi_r"] = self.phi_l
        self["alpha_r"] = self.alpha_l
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
            if self.kind in ("FLAP", "TUBE", "TETHER", "PYRAMID") or m.uid in bad:
                continue
            if self.kind in ("FRAME", "FLOOR", "CEILING"):
                if m.kind == "STAGE":
                    items.append((str(m.uid), m.label, f"Stand in {m.label}",
                                  "IMAGE_BACKGROUND", m.uid))
                continue
            if m.kind == "VFOLD" and self.kind in ("STANDUP", "BOX"):
                items.append((str(m.uid), m.label, f"Stand in front of or behind a half "
                              f"of {m.label}", "MOD_TRIANGULATE", m.uid))
            elif m.kind in ("BOX", "BOXCUT", "STANDUP"):
                items.append((str(m.uid), m.label, f"Sit on a fold of {m.label}",
                              "MESH_CUBE" if m.kind != "STANDUP" else "OUTLINER_OB_IMAGE",
                              m.uid))
            elif m.kind in ("FLOOR", "CEILING"):
                items.append((str(m.uid), m.label, f"Sit in the corner where {m.label} "
                              f"meets a wall", "TRIA_DOWN_BAR" if m.kind == "FLOOR"
                              else "TRIA_UP_BAR", m.uid))
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
        room = {"A": b, "B": a, "C": min(a, b)}[m.fold]
    k = 0.5 * room
    was = st.live
    st["live"] = False
    try:
        if host.kind == "STANDUP":
            w = host.img_w  # the picture is what there is room on
            hy = host.y + 0.5 * host.width - 0.5 * w
        else:
            hy = host.y
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
    finally:
        st["live"] = was


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


class PopupLine(bpy.types.PropertyGroup):
    """An extra crease or cut on a V-fold piece, in the piece's own pattern:
    x across (the centre fold at 0, the left half negative), y up the centre
    fold from the V point (mm)."""
    kind: EnumProperty(name="Kind", items=[
        ("CREASE", "Crease", "Extra fold line"),
        ("CUT", "Cut", "Slit through the paper")], update=_changed)
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

    def points(self):
        if self.path:
            import json
            try:
                return [tuple(q) for q in json.loads(self.path)]
            except ValueError:
                pass
        return [(self.x0, self.y0), (self.x1, self.y1)]


class PopupMech(bpy.types.PropertyGroup):
    uid: IntProperty()
    kind: EnumProperty(items=KINDS, update=_changed)
    label: StringProperty(name="Name", default="Mechanism")
    y: FloatProperty(name="Position", description="Distance up the spine from the "
                     "bottom edge (mm)", default=70.0, min=0.0, soft_max=300.0,
                     update=_changed)
    host_uid: IntProperty(default=0)
    host: EnumProperty(name="Host", description="Fold this mechanism sits on",
                       items=host_items, get=_host_get, set=_host_set)
    fold: EnumProperty(name="Where", items=FOLDS, update=_fold_changed,
                       description="Which fold of the host box")
    # V-fold
    shape: EnumProperty(name="Shape", items=[
        ("QUAD", "Panels", "Each half is a four-sided panel"),
        ("TRI", "Beak", "Each half is a triangle meeting at a point: beaks and mouths")],
        update=_changed)
    # cube
    size: FloatProperty(name="Size", description="Width of each wall (mm)", default=40.0,
                        min=5.0, soft_max=150.0, update=_changed)
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
    tab_side: EnumProperty(name="Tabs", items=[
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
    tab: FloatProperty(name="Tab", description="Glue tab size (mm)", default=12.0,
                       min=3.0, soft_max=30.0, update=_changed)
    vside: EnumProperty(name="Where", description="Which half of the host V-fold, and "
                        "which side of it", items=[
                            ("FL", "In Front, Left", "Stands on the page in front of the "
                             "left half, the half as its background"),
                            ("BL", "Behind, Left", "Inside the V, against the back of the "
                             "left half"),
                            ("FR", "In Front, Right", "Stands on the page in front of the "
                             "right half"),
                            ("BR", "Behind, Right", "Inside the V, against the back of the "
                             "right half")], update=_fold_changed)
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
                 host=self.host_uid, fold=self.fold, side=self.side, vside=self.vside)
        if self.kind == "TUBE":
            d.update(type="TUBE", x=self.x, depth=self.depth, height=self.height,
                     front=self.front, back=self.back, front_style=self.front_style,
                     back_style=self.back_style, tab_side=self.tab_side, roof=self.roof,
                     roof_height=self.roof_height, ridge=self.ridge,
                     roof_fold=self.roof_fold, eave=self.eave, rib=self.rib)
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
                     tab_side=self.tab_side)
        elif self.kind == "FLAP":
            d.update(type="FLAP", side=self.side, x=self.x, hinge=self.hinge,
                     width=self.width, length=self.length, angle=self.angle,
                     strip=self.strip, glue_at=self.glue_at, gap=self.gap,
                     pull_out=self.pull_out)
        elif self.kind == "MOUTH":
            d.update(type="MOUTH", jaw=self.jaw, upper=self.upper, lower=self.lower)
        elif self.kind == "VFOLD":
            d.update(type="VFOLD", phi_l=self.phi_l, alpha_l=self.alpha_l,
                     phi_r=self.phi_l if self.symmetric else self.phi_r,
                     alpha_r=self.alpha_l if self.symmetric else self.alpha_r,
                     glue=self.glue, height=self.height, tab_side=self.tab_side,
                     shape=self.shape,
                     lines=[dict(kind=ln.kind, mirror=ln.mirror, pts=ln.points())
                            for ln in self.lines])
        else:
            d.update(type="BOX", style="CUT" if self.kind == "BOXCUT" else "GLUED",
                     width=self.width, height=self.height, depth=self.depth,
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
                self.on_piece = name
                break
    live.schedule(bpy.context.scene)


class PopupOpening(bpy.types.PropertyGroup):
    label: StringProperty(name="Name", default="Opening")
    on_uid: IntProperty()  # older files: the mechanism (0 = card)
    on_piece: StringProperty(description="The piece the opening is cut in")
    on: EnumProperty(name="Cut In", items=on_items, get=_on_get, set=_on_set,
                     description="The piece the opening is cut in")
    shape: EnumProperty(name="Shape", items=[
        ("RECT", "Rectangle", "Window or plain doorway"),
        ("ARCH", "Arch", "Round-topped doorway or window"),
        ("OVAL", "Oval", "Round or oval window")], update=_opening_changed)
    x: FloatProperty(name="Across", description="Centre, measured across the piece from "
                     "its centre fold (mm; left is negative)", default=0.0,
                     soft_min=-300.0, soft_max=300.0, update=_opening_changed)
    y: FloatProperty(name="Bottom", description="Bottom edge, up from the piece's bottom "
                     "(mm)", default=20.0, soft_min=0.0, soft_max=300.0,
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


class PopupSettings(bpy.types.PropertyGroup):
    size: EnumProperty(name="Card", items=SIZES, default="A5", update=_changed)
    page_depth: FloatProperty(name="Page Width", description="Spine to page edge (mm)",
                              default=148.5, min=20.0, soft_max=400.0, update=_changed)
    spine_length: FloatProperty(name="Spine Length", default=210.0, min=20.0,
                                soft_max=400.0, update=_changed)
    hold: EnumProperty(name="Hold", description="Which page stays still while the card "
                       "opens", items=[
                           ("RIGHT", "Right Page Flat", "Right page lies on the table"),
                           ("LEFT", "Left Page Flat", "Left page lies on the table"),
                           ("SYM", "Both Pages Move", "Spine stays upright")],
                       update=_changed)
    paper: EnumProperty(name="Piece Paper", items=[(k, v[1], "") for k, v in PAPERS.items()],
                        description="Sheet size for the loose pieces", update=_changed)
    mm_per_unit: FloatProperty(name="mm per Unit", description="Millimetres of paper per "
                               "Blender unit (10 = 1 unit is 1 cm)", default=10.0,
                               min=0.01, soft_max=1000.0, update=_changed)
    mechs: CollectionProperty(type=PopupMech)
    active: IntProperty(name="Mechanism")
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
    auto_holes: BoolProperty(name="Cut Painted Areas", default=True,
                             description="Whatever is painted see-through (Erase Alpha) is "
                             "cut out of the paper: holes inside a piece, or a new edge where "
                             "you erase up to its outline. Done on leaving Texture Paint and "
                             "before every export")
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
    solid_paper: BoolProperty(name="Solid Paper", default=False, update=_changed,
                              description="Give the paper real thickness in the viewport and "
                              "renders (Solidify, behind the printed side)")
    anim_frames: IntProperty(name="Frames", description="Frames to open (and close)",
                             default=48, min=2)
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
        if master is not None and master != self.id_data:
            d = master.popup.card_dict()
            d.update(hold="SYM", tmax=360.0 / master.popup.stage_count,
                     piece_sheet=PAPERS[self.paper][0])
            return d
        if self.size == "CUSTOM":
            W, H = self.page_depth, self.spine_length
            sheet = (2 * W, H)
        else:
            W, H, sheet, _, _ = CARD_PRESETS[self.size]
        return dict(W=W, H=H, hold=self.hold, sheet=sheet,
                    piece_sheet=PAPERS[self.paper][0])


classes = (PopupLine, PopupMech, PopupOpening, PopupStageRef, PopupSettings)


def register():
    for c in classes:
        bpy.utils.register_class(c)
    bpy.types.Scene.popup = PointerProperty(type=PopupSettings)


def unregister():
    del bpy.types.Scene.popup
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
