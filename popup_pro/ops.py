import json
import math

import bpy
from bpy.props import EnumProperty, FloatProperty, IntProperty, StringProperty, BoolProperty
from bpy_extras.io_utils import ExportHelper
from mathutils import Quaternion, Vector

from .naming import N
from . import art, build, live


def _scene_ok(context):
    return context.scene is not None


def _rebuild(op, context, force=True):
    try:
        build.rebuild(context.scene, force=force)
    except Exception as ex:
        op.report({"ERROR"}, f"Rebuild failed: {ex}")
        return False
    for w in context.scene.popup.warnings.splitlines():
        op.report({"WARNING"}, w)
    return True


class POPUP_OT_build(bpy.types.Operator):
    """Build (or rebuild) the card, rig and print layout from the settings.
    Resets hand-edited panel shapes"""
    bl_idname = "popup.build"
    bl_label = "Build Card"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        st = context.scene.popup
        first = st.rig is None
        if first and not st.mechs:
            _add(st, "CUBE")  # something to play with: it's Blender after all
        if not _rebuild(self, context):
            return {"CANCELLED"}
        if first:
            st.card.select_set(True)
            context.view_layer.objects.active = st.rig
            _first_setup(context)
        return {"FINISHED"}


def _first_setup(context):
    """The first card (or carousel) in a file sets the scene up for pop-up
    work once; Set Up Scene does it again on demand."""
    from . import scene_setup
    sc = context.scene
    master = sc.popup.stage_master or sc
    if not master.get("pop_setup_done"):
        try:
            scene_setup.setup(context, view_camera=True)
        except (RuntimeError, TypeError, AttributeError, KeyError):
            pass
        # a movement test ready to play: press Play or scrub the timeline
        try:
            bpy.ops.popup.animate(mode="CYCLE")
        except RuntimeError:
            pass


DEFAULTS = {
    "VFOLD": dict(y=70.0, height=50.0, glue=40.0, phi_l=60.0, alpha_l=80.0, tab=12.0),
    "BOX": dict(y=130.0, width=50.0, height=40.0, depth=30.0, tab=12.0),
    "BOXCUT": dict(y=20.0, width=40.0, height=30.0, depth=30.0),
    "MOUTH": dict(y=150.0, jaw=30.0, upper=20.0, lower=15.0),
    "CUBE": dict(y=60.0, size=40.0, height=40.0, tab=10.0),
    "FLAP": dict(y=170.0, x=70.0, width=40.0, length=35.0, tab=8.0),
    "TUBE": dict(y=80.0, x=25.0, depth=40.0, height=50.0, front=30.0, back=30.0, tab=10.0),
    "TETHER": dict(height=30.0, tab=8.0, to_y=40.0),
    "PYRAMID": dict(y=80.0, x=25.0, depth=50.0, height=40.0, ridge=0.0, front=25.0,
                    back=25.0, tab=10.0),
    "FRAME": dict(y=0.0, tab=8.0),
    "STAGE": dict(y=80.0, phi_l=60.0, glue=60.0, height=80.0, tab=10.0, tab_side="OUT"),
    "FLOOR": dict(tab=8.0),
    "CEILING": dict(tab=8.0),
    "STANDUP": dict(y=60.0, width=30.0, height=45.0, depth=30.0, img_w=80.0, img_h=90.0,
                    tab=10.0),
    "ROOF": dict(phi_l=100.0, alpha_l=70.0, glue=150.0, height=60.0, tab=8.0,
                 tab_side="IN"),
}
NAMES = {"VFOLD": "V-fold", "BOX": "Box fold", "BOXCUT": "Box layer", "MOUTH": "Mouth",
         "CUBE": "Cube", "FLAP": "Flap", "TUBE": "Tube", "TETHER": "Tether",
         "PYRAMID": "Pyramid", "FRAME": "Frame", "FLOOR": "Floor", "CEILING": "Ceiling",
         "STAGE": "Stage set", "STANDUP": "Stand-up", "ROOF": "Roof"}


def _add(st, kind):
    # never reuse an id: sketch layers and art tiles are keyed by it
    uid = max([m.uid + 1 for m in st.mechs] + [st.get("pop_next_uid", 1)])
    st["pop_next_uid"] = uid + 1
    was_live = st.live
    st["live"] = False  # no rebuild per property
    m = st.mechs.add()
    m.uid = uid
    m.kind = kind
    n = sum(1 for x in st.mechs if x.kind == kind)
    m.label = f"{NAMES[kind]} {n}"
    H = st.card_dict()["H"]
    for k, v in DEFAULTS[kind].items():
        setattr(m, k, v)
    m.y = min(m.y, max(0.0, H - (m.width if kind in ("BOX", "BOXCUT", "STANDUP") else 0.0) - 10))
    W = st.card_dict()["W"]
    if kind == "FRAME":  # first frame stands at the front of the stage, the rest behind
        n = sum(1 for x in st.mechs if x.kind == "FRAME")
        m.label = "Staging frame" if n == 1 else f"Frame {n - 1}"
        m.x = W - 1.0 if n == 1 else max(10.0, W * (1.0 - 0.25 * (n - 1)))
        m.y, m.height = 0.0, H
    if kind in ("FLOOR", "CEILING"):
        m.depth = W
    if kind == "CUBE":
        m.y = min(m.y, max(0.0, H - m.size * 1.42 - 5))
    if kind == "ROOF":
        m.y = round(0.7 * H, 1)
        # the eaves to the card's side edge
        m.glue = round(W / math.sin(math.radians(m.phi_l)) - 0.5, 1)
    if kind == "FLAP":
        m.y = min(m.y, max(m.tab + m.length, H - 15))
    if kind == "TETHER":
        tubes = [x for x in st.mechs if x.kind == "TUBE"]
        if tubes:  # join the selected (or last) tube's front left corner to a foot
            t = tubes[-1]
            m.from_uid = t.uid
            m.from_pt = "FL"
            m.to = "LEFT"
            m.to_y = max(5.0, t.y - 30.0)
            m.height = 0.6 * t.height
    st["live"] = was_live
    st.active = len(st.mechs) - 1
    return m


class POPUP_OT_add(bpy.types.Operator):
    """Add a pop-up mechanism"""
    bl_idname = "popup.add"
    bl_label = "Add Mechanism"
    bl_options = {"REGISTER", "UNDO"}
    kind: EnumProperty(items=[(k, NAMES[k], "") for k in NAMES])
    host: IntProperty(default=0, description="Mechanism id of the host box (0 = spine)")
    fold: StringProperty(default="A")
    side: StringProperty(default="", description="Wall, for a corner of a floor or ceiling")
    variant: StringProperty(default="", description="ASYM: an asymmetric V-fold; "
                           "VALLEY: a roof upside down; STRAP: a box fold with equal sides "
                           "(gullies off the centre)")

    def execute(self, context):
        st = context.scene.popup
        if self.kind in ("FRAME", "FLOOR", "CEILING"):
            if st.stage_master is None and not self.host:
                stages = [x for x in st.mechs if x.kind == "STAGE"]
                if not stages:
                    self.report({"ERROR"}, "Add a Stage Set first (or make a carousel)")
                    return {"CANCELLED"}
                act = st.mechs[st.active] if st.active < len(st.mechs) else None
                if act is not None and act.kind == "STAGE":
                    self.host = act.uid
                elif act is not None and act.host_uid and any(x.uid == act.host_uid
                                                               for x in stages):
                    self.host = act.host_uid
                else:
                    self.host = stages[-1].uid
            same = [x for x in st.mechs if x.kind == self.kind and x.host_uid == self.host]
            if self.kind == "FRAME" and len(same) >= 4:
                self.report({"ERROR"}, "A stage has a staging frame and up to three frames")
                return {"CANCELLED"}
            if self.kind in ("FLOOR", "CEILING") and same:
                self.report({"ERROR"}, f"This stage already has a {self.kind.lower()}")
                return {"CANCELLED"}
        m = _add(st, self.kind)
        uid = m.uid
        if self.kind == "VFOLD" and self.variant == "ASYM":
            was = st.live
            st["live"] = False
            m.symmetric = False
            m.phi_l, m.phi_r, m.lean, m.fold_flat = 40.0, 75.0, 20.0, True
            m.glue_r = m.glue
            m.label = "Asymmetric " + m.label
            st["live"] = was
        if self.kind == "BOX" and self.variant == "STRAP":
            # Pop-Up Tutorial 9: a glued box fold with equal sides lies flat
            # when the card is open; its two glue folds are gullies away from
            # the spine that open just like it, for pop-ups off the centre
            was = st.live
            st["live"] = False
            H = st.card_dict()["H"]
            m.height = m.depth = 35.0
            m.width = 70.0
            m.y = round(0.5 * H - 35.0, 1)
            m.label = m.label.replace("Box fold", "Strap")
            st["live"] = was
        if self.kind == "ROOF" and self.variant == "VALLEY":
            was = st.live
            st["live"] = False
            m.valley = True
            m.y = round(0.3 * st.card_dict()["H"], 1)
            m.label = m.label.replace("Roof", "Valley floor")
            st["live"] = was
        if self.host:
            if self.side:
                next(x for x in st.mechs if x.uid == uid)["side"] = 1 if self.side == "L" else 0
            _put_on(st, uid, self.host, self.fold)
        if self.kind == "STAGE":  # a staging frame at the front, one frame behind
            for _ in range(2):
                _put_on(st, _add(st, "FRAME").uid, uid, "A")
            st.active = next(i for i, x in enumerate(st.mechs) if x.uid == uid)
        _rebuild(self, context, force=st.rig is not None and not st.edited)
        return {"FINISHED"}


def _put_on(st, uid, host, fold="A"):
    """Stand a new mechanism on a host and size it to fit."""
    from .props import fit_to_host
    was = st.live
    st["live"] = False
    m = next(x for x in st.mechs if x.uid == uid)
    m.host_uid = host
    if fold in ("FL", "BL", "FR", "BR", "V"):  # on a V-fold: a half, or its crease
        m["vside"] = ("FL", "BL", "FR", "BR", "V").index(fold)
        m["on_crease"] = fold == "V"  # (a floor's or ceiling's crease)
    elif fold in ("WL", "WR"):  # outside a cube's or tube's wall
        m["wall"] = 1 if fold == "WL" else 2
    elif fold == "VAL":  # a strap's valley between two peaks
        m["fold"] = 3
    else:
        m["fold"] = {"A": 0, "B": 1, "C": 2}.get(fold, 0)
    fit_to_host(m, st)
    h = next((x for x in st.mechs if x.uid == host), None)
    if m.kind == "FRAME" and h is not None and h.kind == "STAGE":
        n = sum(1 for x in st.mechs if x.kind == "FRAME" and x.host_uid == host)
        m.label = f"{h.label}: staging frame" if n == 1 else f"{h.label}: frame {n - 1}"
    st["live"] = was


class POPUP_OT_remove(bpy.types.Operator):
    """Remove the selected mechanism"""
    bl_idname = "popup.remove"
    bl_label = "Remove Mechanism"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return len(context.scene.popup.mechs) > 0

    def execute(self, context):
        st = context.scene.popup
        st.mechs.remove(st.active)
        st.active = max(0, min(st.active, len(st.mechs) - 1))
        if st.rig is not None:
            _rebuild(self, context)
        return {"FINISHED"}


class POPUP_OT_set_open(bpy.types.Operator):
    """Set how far the card is open"""
    bl_idname = "popup.set_open"
    bl_label = "Set Open Angle"
    bl_options = {"REGISTER", "UNDO"}
    angle: FloatProperty(min=0.0, max=360.0)

    @classmethod
    def poll(cls, context):
        st = context.scene.popup
        return st.rig is not None or st.is_carousel

    def execute(self, context):
        st = context.scene.popup
        if st.is_carousel or st.stage_master is not None:
            from . import carousel
            carousel.set_open(context.scene, self.angle)
            context.view_layer.update()
            return {"FINISHED"}
        rig = st.rig
        rig["pop_open"] = self.angle
        rig.update_tag()
        context.view_layer.update()
        return {"FINISHED"}


def _clear_keys(idb, data_path):
    """Remove an animated property's keys (layered actions in Blender 4.4+,
    plain fcurves before)."""
    ad = idb.animation_data
    if ad is None or ad.action is None:
        return
    fcs = getattr(ad.action, "fcurves", None)
    if fcs is None:
        try:
            from bpy_extras import anim_utils
            cb = anim_utils.action_get_channelbag_for_slot(ad.action, ad.action_slot)
        except (ImportError, AttributeError):
            cb = None
        fcs = cb.fcurves if cb is not None else None
    if fcs is None:
        return
    for fc in [f for f in fcs if f.data_path == data_path]:
        fcs.remove(fc)


def _frames(sc, seconds):
    fps = sc.render.fps / (sc.render.fps_base or 1.0)
    return max(1, int(round(seconds * fps)))


def anim_timing(sc, cycle=True):
    """Frames to open, hold and close, from the movement test settings."""
    st = sc.popup
    return (_frames(sc, st.anim_open), _frames(sc, st.anim_hold) if st.anim_hold > 0 else 0,
            _frames(sc, st.anim_close))


class POPUP_OT_animate(bpy.types.Operator):
    """Keyframe a movement test from the start frame: open to the Open To
    angle, hold, and close, taking the times set below (replaces the last test)"""
    bl_idname = "popup.animate"
    bl_label = "Keyframe Movement Test"
    bl_options = {"REGISTER", "UNDO"}
    mode: EnumProperty(items=[("OPEN", "Open", "Closed to open"),
                              ("CYCLE", "Open and Close", "Closed, open, closed")],
                       default="CYCLE")

    @classmethod
    def poll(cls, context):
        st = context.scene.popup
        return st.rig is not None or st.is_carousel

    def execute(self, context):
        sc = context.scene
        st = sc.popup
        rig, prop, top = st.rig, '["pop_open"]', min(st.anim_to, 180.0)
        if st.is_carousel or st.stage_master is not None:
            from . import carousel  # the carousel's Open drives every stage
            master = st.stage_master or sc
            rig, prop = carousel.ctrl(master), f'["{carousel.OPEN}"]'
            sc = master
            top = sc.popup.anim_to_carousel
        n_open, n_hold, n_close = anim_timing(sc)
        f0 = sc.frame_start
        _clear_keys(rig, prop)
        keys = [(f0, 0.0), (f0 + n_open, top)]
        if self.mode == "CYCLE":
            f = f0 + n_open
            if n_hold:
                f += n_hold
                keys.append((f, top))
            keys.append((f + n_close, 0.0))
        for f, v in keys:
            rig[prop[2:-2]] = v
            rig.keyframe_insert(prop, frame=f)
        sc.frame_end = keys[-1][0]
        sc.frame_set(f0)
        self.report({"INFO"}, f"Movement test: frames {f0} to {keys[-1][0]}, open to {top:g}°")
        return {"FINISHED"}


class POPUP_OT_animate_pull(bpy.types.Operator):
    """Keyframe a pull test for this flap: pull fully out and back in, from the
    current frame"""
    bl_idname = "popup.animate_pull"
    bl_label = "Keyframe Pull Test"
    bl_options = {"REGISTER", "UNDO"}
    uid: IntProperty()

    @classmethod
    def poll(cls, context):
        return context.scene.popup.rig is not None

    def execute(self, context):
        from .build import pull_prop
        sc = context.scene
        rig = sc.popup.rig
        name = pull_prop(self.uid)
        if name not in rig:
            self.report({"ERROR"}, "Rebuild the card first")
            return {"CANCELLED"}
        n_open, n_hold, n_close = anim_timing(sc)
        f0 = sc.frame_current
        _clear_keys(rig, f'["{name}"]')
        keys = [(f0, 0.0), (f0 + n_open, 1.0)]
        if n_hold:
            keys.append((f0 + n_open + n_hold, 1.0))
        keys.append((keys[-1][0] + n_close, 0.0))
        for f, v in keys:
            rig[name] = v
            rig.keyframe_insert(f'["{name}"]', frame=f)
        sc.frame_end = max(sc.frame_end, keys[-1][0])
        sc.frame_set(f0)
        return {"FINISHED"}


class POPUP_OT_add_art(bpy.types.Operator):
    """Add a paint texture (one UDIM tile per piece on the PopupArt UV map)
    to the paper material, ready for Texture Paint or Paint System"""
    bl_idname = "popup.add_art"
    bl_label = "Add Paint Texture"
    bl_options = {"REGISTER", "UNDO"}
    dpi: IntProperty(name="DPI", default=150, min=30, max=600)

    @classmethod
    def poll(cls, context):
        return context.scene.popup.rig is not None

    def execute(self, context):
        try:
            img = art.add_art_texture(context.scene, self.dpi)
        except Exception as ex:
            self.report({"ERROR"}, str(ex))
            return {"CANCELLED"}
        self.report({"INFO"}, f"{img.name}: {len(img.tiles)} tile(s)")
        return {"FINISHED"}


def _view3d(context):
    if context.area and context.area.type == "VIEW_3D":
        return context.area, context.space_data.region_3d
    for area in context.window.screen.areas if context.window else []:
        if area.type == "VIEW_3D":
            return area, area.spaces.active.region_3d
    return None, None


class POPUP_OT_paint(bpy.types.Operator):
    """Paint the artwork in Texture Paint mode, on the flat layout or on the
    folded card"""
    bl_idname = "popup.paint"
    bl_label = "Paint"
    bl_options = {"REGISTER", "UNDO"}
    target: EnumProperty(items=[("LAYOUT", "Flat Layout", ""), ("CARD", "Folded Card", "")])

    @classmethod
    def poll(cls, context):
        return context.scene.popup.card is not None

    def execute(self, context):
        sc = context.scene
        st = sc.popup
        if bpy.data.images.get(N(sc, art.ART_IMAGE)) is None:
            art.add_art_texture(sc)
        if context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        obj = st.layout if self.target == "LAYOUT" else st.card
        for o in context.selected_objects:
            o.select_set(False)
        obj.hide_set(False)
        obj.select_set(True)
        context.view_layer.objects.active = obj
        bpy.ops.object.mode_set(mode="TEXTURE_PAINT")
        from . import colours
        colours.enter(sc)  # (also done on any switch into Texture Paint)
        ip = sc.tool_settings.image_paint
        ip.mode = "MATERIAL"
        if self.target == "LAYOUT":
            area, rv3d = _view3d(context)
            if rv3d is not None:
                meta = live.meta(st.rig)
                sh = meta["sheets"][0]
                mmu = meta["mm_per_unit"]
                rv3d.view_rotation = Quaternion((1, 0, 0, 0))
                rv3d.view_location = Vector(((sh["origin"][0] + sh["size"][0] / 2) / mmu,
                                             (sh["origin"][1] + sh["size"][1] / 2) / mmu, 0))
                rv3d.view_distance = max(sh["size"]) / mmu * 1.1
                rv3d.view_perspective = "ORTHO"
        return {"FINISHED"}


class POPUP_OT_sketch(bpy.types.Operator):
    """Draw with Grease Pencil on a panel. Strokes go on a layer parented to
    the panel, so they move with it"""
    bl_idname = "popup.sketch"
    bl_label = "Sketch on Panel"
    bl_options = {"REGISTER", "UNDO"}
    panel: StringProperty()
    align: BoolProperty(name="Align View", default=True)
    cut: BoolProperty(name="Holes", default=False,
                      description="Draw closed outlines that are cut out of the panel")

    @classmethod
    def poll(cls, context):
        return context.scene.popup.rig is not None

    def execute(self, context):
        sc = context.scene
        st = sc.popup
        panel = self.panel or st.sketch_panel
        if panel not in st.rig.pose.bones:
            self.report({"ERROR"}, "Pick a panel (build the card first)")
            return {"CANCELLED"}
        if context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        obj, layer = art.sketch_layer(sc, panel, cut=self.cut)
        for o in context.selected_objects:
            o.select_set(False)
        obj.hide_set(False)
        obj.select_set(True)
        context.view_layer.objects.active = obj
        ts = sc.tool_settings
        ts.gpencil_stroke_placement_view3d = "SURFACE"
        ts.gpencil_surface_offset = 0.25 / st.mm_per_unit
        try:
            bpy.ops.object.mode_set(mode="PAINT_GREASE_PENCIL")
        except (RuntimeError, TypeError):
            pass
        if self.align:
            area, rv3d = _view3d(context)
            if rv3d is not None:
                M, centre, normal = art.panel_view(sc, panel)
                q = normal.to_track_quat("Z", "Y")
                rv3d.view_rotation = q
                rv3d.view_location = centre
                rv3d.view_distance = 120.0 / st.mm_per_unit
        return {"FINISHED"}


class POPUP_OT_bake(bpy.types.Operator):
    """Bake the card's material colour (Texture Paint, Paint System or any
    shader) into the Pop-up Print image used by the SVG export. Uses Cycles"""
    bl_idname = "popup.bake"
    bl_label = "Bake Art for Print"
    bl_options = {"REGISTER", "UNDO"}
    dpi: IntProperty(name="DPI", default=150, min=30, max=600)

    @classmethod
    def poll(cls, context):
        return context.scene.popup.rig is not None

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        try:
            art.bake_art(context.scene, self.dpi)
        except Exception as ex:
            self.report({"ERROR"}, f"Bake failed: {ex}")
            return {"CANCELLED"}
        notes = []
        if getattr(art.bake_art, "last_pass", "BASE") == "EMIT":
            notes.append("baked the emission colour (the material colours through emission)")
        if getattr(art.bake_art, "textures_fixed", False):
            notes.append("decoded sRGB paint textures for Cycles (this Blender skips it)")
        self.report({"INFO"}, "Baked" + (": " + "; ".join(notes) if notes else ""))
        return {"FINISHED"}


class POPUP_OT_export_svg(bpy.types.Operator, ExportHelper):
    """Export one SVG per sheet using the Export settings: print sheets with
    art, or cut / crease lines only for a cutting machine"""
    bl_idname = "popup.export_svg"
    bl_label = "Export SVG Sheets"
    filename_ext = ".svg"
    filter_glob: StringProperty(default="*.svg", options={"HIDDEN"})

    @classmethod
    def poll(cls, context):
        return context.scene.popup.rig is not None

    def draw(self, context):
        from .ui import draw_export
        draw_export(self.layout, context.scene.popup)

    def execute(self, context):
        from . import export_svg, holes
        st = context.scene.popup
        try:
            if st.auto_holes and not st.edited:
                holes.cut_painted(context.scene)  # print the shape the paint shows
            files = export_svg.export(context.scene, self.filepath,
                                      **export_svg.settings_from(st))
        except Exception as ex:
            self.report({"ERROR"}, f"Export failed: {ex}")
            return {"CANCELLED"}
        self.report({"INFO"}, f"Wrote {len(files)} sheet(s)")
        return {"FINISHED"}


class POPUP_OT_view_layout(bpy.types.Operator):
    """Look straight down on the print sheets"""
    bl_idname = "popup.view_layout"
    bl_label = "View Layout"

    @classmethod
    def poll(cls, context):
        return context.scene.popup.rig is not None

    def execute(self, context):
        st = context.scene.popup
        meta = live.meta(st.rig)
        area, rv3d = _view3d(context)
        if meta is None or rv3d is None:
            return {"CANCELLED"}
        mmu = meta["mm_per_unit"]
        sh = meta["sheets"]
        x0 = sh[0]["origin"][0]
        x1 = sh[-1]["origin"][0] + sh[-1]["size"][0]
        y0 = min(s["origin"][1] for s in sh)
        y1 = max(s["origin"][1] + s["size"][1] for s in sh)
        rv3d.view_rotation = Quaternion((1, 0, 0, 0))
        rv3d.view_location = Vector(((x0 + x1) / 2 / mmu, (y0 + y1) / 2 / mmu, 0))
        rv3d.view_distance = max(x1 - x0, y1 - y0) / mmu * 1.05
        rv3d.view_perspective = "ORTHO"
        return {"FINISHED"}


class POPUP_OT_make_carousel(bpy.types.Operator):
    """Make this scene a carousel: a stage scene for each stage (each a Pop-Up
    card of its own, opening to 360 / Stages degrees), shown together round
    one spine"""
    bl_idname = "popup.make_carousel"
    bl_label = "Make Carousel"
    bl_options = {"REGISTER", "UNDO"}
    count: IntProperty(name="Stages", default=5, min=2, max=9)

    @classmethod
    def poll(cls, context):
        st = context.scene.popup
        return st.stage_master is None and st.rig is None

    def execute(self, context):
        from . import carousel
        carousel.make(context.scene, self.count)
        context.scene.frame_set(context.scene.frame_current)
        _first_setup(context)
        return {"FINISHED"}


class POPUP_OT_goto_stage(bpy.types.Operator):
    """Edit one stage on its own (0: back to the whole carousel)"""
    bl_idname = "popup.goto_stage"
    bl_label = "Go to Stage"
    index: IntProperty(default=0)

    def execute(self, context):
        from . import carousel
        st = context.scene.popup
        master = st.stage_master or context.scene
        if self.index == 0:
            carousel.goto(context, master)
            return {"FINISHED"}
        sts = carousel.stages(master)
        if not 1 <= self.index <= len(sts):
            return {"CANCELLED"}
        carousel.goto(context, sts[self.index - 1])
        return {"FINISHED"}


class POPUP_OT_carousel_sync(bpy.types.Operator):
    """Rebuild every stage and the carousel"""
    bl_idname = "popup.carousel_sync"
    bl_label = "Rebuild Carousel"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        from . import carousel
        carousel.make(context.scene.popup.stage_master or context.scene)
        return {"FINISHED"}


class POPUP_OT_export_carousel(bpy.types.Operator, ExportHelper):
    """Export every stage of the carousel (and its leaves, for shared pages)"""
    bl_idname = "popup.export_carousel"
    bl_label = "Export Carousel SVG"
    filename_ext = ".svg"

    def invoke(self, context, event):
        if not self.filepath:
            self.filepath = bpy.path.ensure_ext(
                bpy.path.abspath("//") + context.scene.name, ".svg")
        return ExportHelper.invoke(self, context, event)

    def draw(self, context):
        from .ui import draw_export
        draw_export(self.layout, context.scene.popup)

    def execute(self, context):
        from . import carousel, export_svg
        sc = context.scene
        master = sc.popup.stage_master or sc
        try:
            from . import holes
            for stage in carousel.stages(master):
                if stage.popup.auto_holes and not stage.popup.edited:
                    with carousel.in_scene(stage):
                        holes.cut_painted(stage)
            files = carousel.export(master, self.filepath,
                                    **export_svg.settings_from(master.popup))
        except RuntimeError as ex:
            self.report({"ERROR"}, str(ex))
            return {"CANCELLED"}
        self.report({"INFO"}, f"Wrote {len(files)} file(s)")
        return {"FINISHED"}


class POPUP_OT_add_opening(bpy.types.Operator):
    """Add a window, doorway or arch cut through the paper"""
    bl_idname = "popup.add_opening"
    bl_label = "Add Opening"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        st = context.scene.popup
        o = st.openings.add()
        o.label = f"Opening {len(st.openings)}"
        # on the selected mechanism if it can take one, else the card
        o.on_piece = "Card"
        meta = live.meta(st.rig)
        if st.mechs and st.active < len(st.mechs) and meta:
            m = st.mechs[st.active]
            # the selected mechanism's own piece, if it has one
            for name, info in meta["pieces"].items():
                if not info["is_card"] and int(info["slot"]) == 1 + m.uid:
                    o.on_piece = name
        if o.on_piece == "Card":
            o.x = 0.5 * st.card_dict()["W"]
        st.active_opening = len(st.openings) - 1
        live.schedule(context.scene)
        return {"FINISHED"}


class POPUP_OT_remove_opening(bpy.types.Operator):
    """Remove the selected opening"""
    bl_idname = "popup.remove_opening"
    bl_label = "Remove Opening"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        st = context.scene.popup
        if 0 <= st.active_opening < len(st.openings):
            o = st.openings[st.active_opening]
            o.through = "NONE"  # neighbours lose it too
            st.openings.remove(st.active_opening)
            st.active_opening = max(0, st.active_opening - 1)
        live.schedule(context.scene)
        return {"FINISHED"}


class POPUP_OT_draw_holes(bpy.types.Operator):
    """Draw hole outlines with Grease Pencil straight onto the flat layout (any
    piece, either half of a fold). Closed strokes are cut at the next rebuild"""
    bl_idname = "popup.draw_holes"
    bl_label = "Draw Holes"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.scene.popup.layout is not None

    def execute(self, context):
        from . import holes
        sc = context.scene
        st = sc.popup
        if context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        obj, layer = holes.hole_sketch(sc)
        obj.data.layers.active = layer
        obj.active_material_index = len(obj.data.materials) - 1
        st.layout.hide_set(False)
        for o in context.selected_objects:
            o.select_set(False)
        obj.hide_set(False)
        obj.select_set(True)
        context.view_layer.objects.active = obj
        ts = sc.tool_settings
        ts.gpencil_stroke_placement_view3d = "SURFACE"
        ts.gpencil_surface_offset = 0.2 / st.mm_per_unit
        try:
            bpy.ops.object.mode_set(mode="PAINT_GREASE_PENCIL")
        except (RuntimeError, TypeError):
            pass
        area, rv3d = _view3d(context)
        if rv3d is not None:  # look straight down on the layout
            bb = [st.layout.matrix_world @ Vector(c) for c in st.layout.bound_box]
            mid = sum(bb, Vector()) / 8.0
            rv3d.view_rotation = Quaternion((1, 0, 0, 0))
            rv3d.view_location = mid
            rv3d.view_perspective = "ORTHO"
        return {"FINISHED"}


class POPUP_OT_keep_holes(bpy.types.Operator):
    """Fix the drawn hole outlines onto their pieces (they then stay with them
    when the layout is rearranged) and clear the strokes. Edit brings them
    back as strokes"""
    bl_idname = "popup.keep_holes"
    bl_label = "Keep Drawn Holes"
    bl_options = {"REGISTER", "UNDO"}
    edit: BoolProperty(default=False)

    @classmethod
    def poll(cls, context):
        return context.scene.popup.rig is not None

    def execute(self, context):
        from . import holes
        sc = context.scene
        if context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        model, layout = build.make_model(sc)
        if self.edit:
            n = holes.edit_kept(sc, model, layout)
            build.rebuild(sc, force=True)
            self.report({"INFO"}, f"{n} hole outline(s) back as strokes")
            return {"FINISHED"}
        n = holes.keep_drawn(sc, model, layout)
        build.rebuild(sc, force=True)
        self.report({"INFO"}, f"{n} hole(s) kept")
        return {"FINISHED"}


LINE_PRESETS = [
    ("NONE", "Line", "A plain line to set by numbers"),
    ("REVERSE", "Reverse Point", "Two creases and a cut: a point folding forward out of "
     "the V (Birmingham 5, angles A)"),
    ("STEP", "Step", "Creases parallel to the centre fold and a cut: a stepped top "
     "(Birmingham 5, lengths B)"),
    ("TOP", "Folded Top", "Two creases from the centre fold to the top edge: the top "
     "folds back (Birmingham 5, angles C)"),
    ("JAW", "Jaw", "Creases from the centre fold out to the sides, the centre fold "
     "turning from mountain to valley: a chomping jaw (Birmingham 9 and 10)"),
    ("PROJECTION", "Projection", "A cut starting and ending on the centre fold, on one "
     "half only: the shape juts out flat past the fold (Birmingham 6)"),
]
BOX_PRESETS = [
    ("NONE", "Line", "A plain line to set by numbers"),
    ("BATTLEMENTS", "Battlements", "Notches cut along the front's top fold: the "
     "merlons stand up above the top (Birmingham 37, the castle)"),
    ("TOWER", "Pointed Tower", "A pointed shape cut into the top from the front's top "
     "fold: it stands up above the box like a spire"),
    ("DOORWAY", "Doorway", "An arch cut up from the front's bottom fold: the door stays "
     "flat on the floor, leaving an opening"),
    ("INSET", "Inset Step", "Two creases and two cuts across the front-top fold: that "
     "part folds in (a step back)"),
]


def _lined_active(context):
    st = context.scene.popup
    if 0 <= st.active < len(st.mechs) and st.mechs[st.active].kind in ("VFOLD", "BOX",
                                                                         "BOXCUT", "ROOF"):
        return st.mechs[st.active]
    return None


_vfold_active = _lined_active


def _preset_items(self, context):
    m = _lined_active(context) if context else None
    return BOX_PRESETS if m is not None and m.kind in ("BOX", "BOXCUT") else LINE_PRESETS


def _arch(x0, yc, r, hgt, seg=8):
    """Arch outline from the fold at x0, rising toward -x (box front)."""
    top = x0 - max(hgt - r, 0.0)
    pts = [(x0, yc - r), (top, yc - r)]
    pts += [(top - r * math.sin(math.pi * i / seg), yc - r * math.cos(math.pi * i / seg))
            for i in range(1, seg)]
    return pts + [(top, yc + r), (x0, yc + r)]


class POPUP_OT_add_line(bpy.types.Operator):
    """Add an extra crease or cut (a V-fold: on its left half; a box: measured
    from its front-top fold). Mirror copies it onto the other side"""
    bl_idname = "popup.add_line"
    bl_label = "Add Crease or Cut"
    bl_options = {"REGISTER", "UNDO"}
    preset: EnumProperty(name="Shape", items=_preset_items)

    @classmethod
    def poll(cls, context):
        return _lined_active(context) is not None

    def execute(self, context):
        m = _lined_active(context)
        if m.kind in ("VFOLD", "ROOF"):
            w = m.glue * math.sin(math.radians(m.alpha_l))
            h = m.height
            t15 = math.tan(math.radians(15))
            P = {
                "NONE": [("CREASE", True, [(0.0, 0.6 * h), (-0.5 * w, 0.4 * h)])],
                "REVERSE": [("CREASE", True, [(0.0, 0.8 * h), (-0.35 * w, 0.45 * h)]),
                            ("CUT", True, [(0.0, 0.45 * h), (-0.35 * w, 0.45 * h)])],
                "STEP": [("CREASE", True, [(-0.3 * w, 1.5 * h), (-0.3 * w, 0.55 * h)]),
                         ("CUT", True, [(0.0, 0.55 * h), (-0.3 * w, 0.55 * h)])],
                "TOP": [("CREASE", True, [(0.0, 0.5 * h), (-0.45 * w, 1.5 * h)])],
                "JAW": [("CREASE", True, [(0.0, 0.5 * h),
                                          (-1.3 * w, 0.5 * h + 1.3 * w * t15)])],
                "PROJECTION": [("CUT", False, [(0.0, 0.55 * h), (-0.25 * w, 0.6 * h),
                                               (-0.25 * w, 0.85 * h), (0.0, 0.9 * h)])],
            }.get(self.preset)
        else:
            a, b, w = m.height, m.depth, m.width  # front, top, along
            P = None
            if self.preset == "NONE":
                P = [("CUT", True, [(0.0, 0.3 * w), (-0.3 * b, 0.3 * w)])]
            elif self.preset == "BATTLEMENTS":
                n = max(2, int(round(w / 14.0)))
                gap = w / (2 * n + 1)
                hh = min(0.3 * b, 8.0)
                P = [("CUT", False, [(0.0, gap * (2 * i + 1)), (-hh, gap * (2 * i + 1)),
                                     (-hh, gap * (2 * i + 2)), (0.0, gap * (2 * i + 2))])
                     for i in range(n)]
            elif self.preset == "TOWER":
                r, hh = 0.15 * w, 0.8 * b
                P = [("CUT", False, [(0.0, 0.5 * w - r), (-0.6 * hh, 0.5 * w - r),
                                     (-hh, 0.5 * w), (-0.6 * hh, 0.5 * w + r),
                                     (0.0, 0.5 * w + r)])]
            elif self.preset == "DOORWAY":
                P = [("CUT", False, _arch(a, 0.5 * w, min(0.15 * w, 0.3 * a), 0.6 * a))]
            elif self.preset == "INSET":
                e = 0.3 * min(a, b)
                P = [("CREASE", False, [(-e, 0.3 * w), (-e, 0.7 * w)]),
                     ("CREASE", False, [(e, 0.3 * w), (e, 0.7 * w)]),
                     ("CUT", True, [(-e, 0.3 * w), (e, 0.3 * w)])]
            if P is None:
                return {"CANCELLED"}
        for kind, mirror, pts in P:
            ln = m.lines.add()
            ln.kind, ln.mirror = kind, mirror
            (ln.x0, ln.y0), (ln.x1, ln.y1) = pts[0], pts[-1]
            if len(pts) > 2:
                ln.path = json.dumps([(round(x, 3), round(y, 3)) for x, y in pts])
        m.active_line = len(m.lines) - 1
        live.schedule(context.scene)
        return {"FINISHED"}


class POPUP_OT_remove_line(bpy.types.Operator):
    """Remove the selected extra crease or cut"""
    bl_idname = "popup.remove_line"
    bl_label = "Remove Line"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        m = _vfold_active(context)
        return m is not None and 0 <= m.active_line < len(m.lines)

    def execute(self, context):
        m = _vfold_active(context)
        m.lines.remove(m.active_line)
        m.active_line = max(0, min(m.active_line, len(m.lines) - 1))
        live.schedule(context.scene)
        return {"FINISHED"}


CARD_PRESETS_LINES = [
    ("PEAKED", "Peaked Roof", "The background's top, cut apart at the spine and joined "
     "again by a glue tab: it folds in over the stage as a peaked roof, its ridge level "
     "when the stage is fully open (change the Join Tab's angle to tilt the ridge, the "
     "creases' to change the pitch)"),
    ("CEILING", "Hanging Ceiling", "Two creases rising from the spine to the top edge: the "
     "top of the background folds in over the stage and hangs down at the centre"),
    ("FLOOR", "Floor", "Two creases falling from the spine to the bottom edge: the bottom "
     "of the background folds in as a floor"),
    ("NONE", "Line", "A plain crease to set by numbers"),
]


class POPUP_OT_add_card_line(bpy.types.Operator):
    """Add an extra crease or cut to the card itself (the background): x across
    the card from the spine (left page negative), y up from the bottom edge"""
    bl_idname = "popup.add_card_line"
    bl_label = "Add Crease or Cut to the Card"
    bl_options = {"REGISTER", "UNDO"}
    preset: EnumProperty(name="Shape", items=CARD_PRESETS_LINES)

    def execute(self, context):
        st = context.scene.popup
        card = st.card_dict()
        W, H = card["W"], card["H"]
        tmax = float(card.get("tmax", 180.0))
        # folded in from the spine, it lies closest to level at the stage's
        # full opening with these angles
        phi = math.radians(60.0 if tmax >= 100.0 else 50.0)
        sx, cy = math.sin(phi), math.cos(phi)
        L = 2.0 * max(W, H)
        if self.preset == "CEILING":
            y0 = 0.75 * H
            pts = [(0.0, y0), (-L * sx, y0 + L * cy)]
        elif self.preset == "FLOOR":
            y0 = 0.25 * H
            pts = [(0.0, y0), (-L * sx, y0 - L * cy)]
        else:
            pts = [(0.0, 0.5 * H), (-0.5 * W, 0.5 * H)]
        if self.preset == "PEAKED":
            y0 = 0.8 * H
            # with the eaves 10 degrees below level, this join angle keeps the
            # ridge level at the stage's full opening
            psi = max(5.0, min(80.0, 99.0 - 0.5 * tmax))
            for kind, mirror, ang, x0 in (("CREASE", True, 100.0, 0.0),
                                          ("JOIN", True, psi, 0.0)):
                ln = st.card_lines.add()
                ln.kind, ln.mirror, ln.by_angle = kind, mirror, True
                ln.x0, ln.y0, ln.angle, ln.length = x0, y0, ang, L
            ln = st.card_lines.add()
            ln.kind, ln.mirror = "CUT", False
            (ln.x0, ln.y0), (ln.x1, ln.y1) = (0.0, y0), (0.0, H + 5.0)
            st.active_card_line = len(st.card_lines) - 3
            live.schedule(context.scene)
            return {"FINISHED"}
        ln = st.card_lines.add()
        ln.kind, ln.mirror, ln.by_angle = "CREASE", True, True
        (ln.x0, ln.y0) = pts[0]
        ln.length = L
        dx, dy = pts[1][0] - pts[0][0], pts[1][1] - pts[0][1]
        ln.angle = math.degrees(math.atan2(-dx, dy))
        st.active_card_line = len(st.card_lines) - 1
        live.schedule(context.scene)
        return {"FINISHED"}


class POPUP_OT_remove_card_line(bpy.types.Operator):
    """Remove the selected crease or cut from the card"""
    bl_idname = "popup.remove_card_line"
    bl_label = "Remove Card Line"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        st = context.scene.popup
        return 0 <= st.active_card_line < len(st.card_lines)

    def execute(self, context):
        st = context.scene.popup
        st.card_lines.remove(st.active_card_line)
        st.active_card_line = max(0, min(st.active_card_line, len(st.card_lines) - 1))
        live.schedule(context.scene)
        return {"FINISHED"}


class POPUP_OT_draw_lines(bpy.types.Operator):
    """Draw extra creases (straightened end to end) or cuts with Grease Pencil
    on the V-fold pieces in the flat layout, then press Add Drawn Lines"""
    bl_idname = "popup.draw_lines"
    bl_label = "Draw Lines"
    bl_options = {"REGISTER", "UNDO"}
    kind: EnumProperty(items=[("CREASE", "Creases", ""), ("CUT", "Cuts", "")])

    @classmethod
    def poll(cls, context):
        return context.scene.popup.layout is not None

    def execute(self, context):
        from . import holes
        sc = context.scene
        st = sc.popup
        if context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        obj, layer = holes.line_layer(sc, self.kind)
        st.layout.hide_set(False)
        for o in context.selected_objects:
            o.select_set(False)
        obj.hide_set(False)
        obj.select_set(True)
        context.view_layer.objects.active = obj
        ts = sc.tool_settings
        ts.gpencil_stroke_placement_view3d = "SURFACE"
        ts.gpencil_surface_offset = 0.2 / st.mm_per_unit
        try:
            bpy.ops.object.mode_set(mode="PAINT_GREASE_PENCIL")
        except (RuntimeError, TypeError):
            pass
        area, rv3d = _view3d(context)
        if rv3d is not None:
            bb = [st.layout.matrix_world @ Vector(c) for c in st.layout.bound_box]
            rv3d.view_rotation = Quaternion((1, 0, 0, 0))
            rv3d.view_location = sum(bb, Vector()) / 8.0
            rv3d.view_perspective = "ORTHO"
        return {"FINISHED"}


class POPUP_OT_take_lines(bpy.types.Operator):
    """Turn the drawn creases and cuts into extra lines on the V-folds they were
    drawn on (Mirror as set below) and clear the strokes"""
    bl_idname = "popup.take_lines"
    bl_label = "Add Drawn Lines"
    bl_options = {"REGISTER", "UNDO"}
    mirror: BoolProperty(name="Mirror", default=True)

    @classmethod
    def poll(cls, context):
        return context.scene.popup.rig is not None

    def execute(self, context):
        from . import holes
        sc = context.scene
        if context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        model, layout = build.make_model(sc)
        got, miss = holes.take_lines(sc, model, layout, self.mirror)
        build.rebuild(sc, force=True)
        msg = f"{got} line(s) added"
        if miss:
            msg += f"; {miss} not on a V-fold piece, dropped"
        self.report({"INFO"} if not miss else {"WARNING"}, msg)
        return {"FINISHED"}


class POPUP_OT_trace_holes(bpy.types.Operator):
    """Cut out everything painted see-through in the art (paint with Erase
    Alpha in Texture Paint). Run again after repainting"""
    bl_idname = "popup.trace_holes"
    bl_label = "Cut Painted Holes"
    bl_options = {"REGISTER", "UNDO"}
    clear: BoolProperty(default=False)

    @classmethod
    def poll(cls, context):
        return context.scene.popup.rig is not None

    def execute(self, context):
        from . import holes
        sc = context.scene
        if self.clear:
            sc.popup["pop_painted"] = "{}"
            n = 0
        else:
            try:
                n = holes.trace_painted(sc)
            except RuntimeError as ex:
                self.report({"ERROR"}, str(ex))
                return {"CANCELLED"}
        build.rebuild(sc, force=True)
        self.report({"INFO"}, f"{n} painted hole(s)")
        return {"FINISHED"}


classes = (POPUP_OT_add_card_line, POPUP_OT_remove_card_line, POPUP_OT_add_line,
           POPUP_OT_remove_line, POPUP_OT_draw_lines,
           POPUP_OT_take_lines, POPUP_OT_draw_holes, POPUP_OT_keep_holes, POPUP_OT_export_carousel,
           POPUP_OT_add_opening, POPUP_OT_remove_opening, POPUP_OT_trace_holes,
           POPUP_OT_make_carousel, POPUP_OT_goto_stage, POPUP_OT_carousel_sync,
           POPUP_OT_build, POPUP_OT_add, POPUP_OT_remove, POPUP_OT_set_open,
           POPUP_OT_animate, POPUP_OT_animate_pull, POPUP_OT_add_art, POPUP_OT_paint, POPUP_OT_sketch,
           POPUP_OT_bake, POPUP_OT_export_svg, POPUP_OT_view_layout)


def register():
    for c in classes:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
