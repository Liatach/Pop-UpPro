import math

import bpy
from bpy.props import EnumProperty, FloatProperty, IntProperty, StringProperty, BoolProperty
from bpy_extras.io_utils import ExportHelper
from mathutils import Quaternion, Vector

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
            _add(st, "VFOLD")
            _add(st, "BOX")
        if not _rebuild(self, context):
            return {"CANCELLED"}
        if first:
            st.card.select_set(True)
            context.view_layer.objects.active = st.rig
        return {"FINISHED"}


DEFAULTS = {
    "VFOLD": dict(y=70.0, height=50.0, glue=40.0, phi_l=60.0, alpha_l=80.0, tab=12.0),
    "BOX": dict(y=130.0, width=50.0, height=40.0, depth=30.0, tab=12.0),
    "BOXCUT": dict(y=20.0, width=40.0, height=30.0, depth=30.0),
    "MOUTH": dict(y=150.0, jaw=30.0, upper=20.0, lower=15.0),
    "CUBE": dict(y=60.0, size=40.0, height=40.0, tab=10.0),
    "FLAP": dict(y=170.0, x=70.0, width=40.0, length=35.0, tab=8.0),
    "TUBE": dict(y=80.0, x=25.0, depth=40.0, height=50.0, front=30.0, back=30.0, tab=10.0),
    "TETHER": dict(height=30.0, tab=8.0, to_y=40.0),
}
NAMES = {"VFOLD": "V-fold", "BOX": "Box fold", "BOXCUT": "Box layer", "MOUTH": "Mouth",
         "CUBE": "Cube", "FLAP": "Flap", "TUBE": "Tube", "TETHER": "Tether"}


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
    m.y = min(m.y, max(0.0, H - (m.width if kind in ("BOX", "BOXCUT") else 0.0) - 10))
    if kind == "CUBE":
        m.y = min(m.y, max(0.0, H - m.size * 1.42 - 5))
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

    def execute(self, context):
        st = context.scene.popup
        m = _add(st, self.kind)
        if self.host:
            from .props import fit_to_host
            was = st.live
            st["live"] = False
            m.host_uid = self.host
            m["fold"] = {"A": 0, "B": 1, "C": 2}.get(self.fold, 0)
            fit_to_host(m, st)
            st["live"] = was
        _rebuild(self, context, force=st.rig is not None and not st.edited)
        return {"FINISHED"}


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
    angle: FloatProperty(min=0.0, max=180.0)

    @classmethod
    def poll(cls, context):
        return context.scene.popup.rig is not None

    def execute(self, context):
        rig = context.scene.popup.rig
        rig["pop_open"] = self.angle
        rig.update_tag()
        context.view_layer.update()
        return {"FINISHED"}


class POPUP_OT_animate(bpy.types.Operator):
    """Keyframe the card opening flat and closing again from the start frame
    (a movement test)"""
    bl_idname = "popup.animate"
    bl_label = "Keyframe Movement Test"
    bl_options = {"REGISTER", "UNDO"}
    mode: EnumProperty(items=[("OPEN", "Open", "Closed to flat"),
                              ("CYCLE", "Open and Close", "Closed, flat, closed")],
                       default="CYCLE")

    @classmethod
    def poll(cls, context):
        return context.scene.popup.rig is not None

    def execute(self, context):
        sc = context.scene
        rig = sc.popup.rig
        n = sc.popup.anim_frames
        f0 = sc.frame_start
        ad = rig.animation_data
        if ad and ad.action:
            for fc in list(getattr(ad.action, "fcurves", [])):
                if fc.data_path == '["pop_open"]':
                    ad.action.fcurves.remove(fc)
        keys = [(f0, 0.0), (f0 + n, 180.0)]
        if self.mode == "CYCLE":
            hold = max(1, n // 4)
            keys += [(f0 + n + hold, 180.0), (f0 + 2 * n + hold, 0.0)]
        for f, v in keys:
            rig["pop_open"] = v
            rig.keyframe_insert('["pop_open"]', frame=f)
        sc.frame_end = keys[-1][0]
        sc.frame_set(f0)
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
        n = sc.popup.anim_frames
        f0 = sc.frame_current
        for f, v in ((f0, 0.0), (f0 + n // 2, 1.0), (f0 + n // 2 + max(1, n // 4), 1.0),
                     (f0 + n + max(1, n // 4), 0.0)):
            rig[name] = v
            rig.keyframe_insert(f'["{name}"]', frame=f)
        sc.frame_end = max(sc.frame_end, f0 + n + max(1, n // 4))
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
        if bpy.data.images.get(art.ART_IMAGE) is None:
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
        obj, layer = art.sketch_layer(sc, panel)
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
        from . import export_svg
        st = context.scene.popup
        try:
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


classes = (POPUP_OT_build, POPUP_OT_add, POPUP_OT_remove, POPUP_OT_set_open,
           POPUP_OT_animate, POPUP_OT_animate_pull, POPUP_OT_add_art, POPUP_OT_paint, POPUP_OT_sketch,
           POPUP_OT_bake, POPUP_OT_export_svg, POPUP_OT_view_layout)


def register():
    for c in classes:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
