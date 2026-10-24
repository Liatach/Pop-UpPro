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
]

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
            if m.kind in ("BOX", "BOXCUT") and m.uid not in bad and self.kind != "FLAP":
                items.append((str(m.uid), m.label, f"Sit on a fold of {m.label}",
                              "MESH_CUBE", m.uid))
    _host_items = items
    return _host_items


def _host_get(self):
    return self.host_uid


def fit_to_host(m, st):
    """Size a mechanism to sit inside the host-box fold it was just put on:
    half the host's panels, centred along it, so there's paper left round it
    to read as a step or an inset."""
    host = next((h for h in st.mechs if h.uid == m.host_uid), None)
    if host is None or host.kind not in ("BOX", "BOXCUT"):
        return
    a, b, w = host.height, host.depth, host.width  # left page, right page, along spine
    room = {"A": b, "B": a, "C": min(a, b)}[m.fold]
    k = 0.5 * room
    was = st.live
    st["live"] = False
    try:
        if m.kind in ("BOX", "BOXCUT"):
            m.height = m.depth = k
            m.width = 0.5 * w
            m.y = host.y + 0.25 * w
        elif m.kind == "VFOLD":
            m.height = m.glue = 0.8 * k
            m.y = host.y + 0.25 * w
        elif m.kind == "MOUTH":
            m.jaw = 0.6 * k
            m.upper = m.lower = min(0.25 * w, 0.6 * k)
            m.y = host.y + 0.5 * w
        elif m.kind == "CUBE":
            m.size = m.height = 0.6 * k
            m.y = host.y + 0.25 * w
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

    def to_dict(self):
        d = dict(uid=self.uid, label=self.label, y=self.y, tab=self.tab,
                 host=self.host_uid, fold=self.fold)
        if self.kind == "CUBE":
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
                     shape=self.shape)
        else:
            d.update(type="BOX", style="CUT" if self.kind == "BOXCUT" else "GLUED",
                     width=self.width, height=self.height, depth=self.depth)
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

    def card_dict(self):
        from .core.model import CARD_PRESETS
        if self.size == "CUSTOM":
            W, H = self.page_depth, self.spine_length
            sheet = (2 * W, H)
        else:
            W, H, sheet, _, _ = CARD_PRESETS[self.size]
        return dict(W=W, H=H, hold=self.hold, sheet=sheet,
                    piece_sheet=PAPERS[self.paper][0])


classes = (PopupMech, PopupSettings)


def register():
    for c in classes:
        bpy.utils.register_class(c)
    bpy.types.Scene.popup = PointerProperty(type=PopupSettings)


def unregister():
    del bpy.types.Scene.popup
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
