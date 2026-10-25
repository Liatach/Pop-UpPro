import bpy

from . import live
from .naming import N

KIND_ICON = {"VFOLD": "MOD_TRIANGULATE", "BOX": "MESH_CUBE", "BOXCUT": "SNAP_FACE",
             "MOUTH": "MOD_SIMPLEDEFORM", "CUBE": "CUBE", "FLAP": "MOD_CLOTH",
             "TUBE": "MESH_CYLINDER", "TETHER": "LINKED",
             "PYRAMID": "CONE", "FRAME": "IMAGE_PLANE", "FLOOR": "TRIA_DOWN_BAR",
             "CEILING": "TRIA_UP_BAR", "STAGE": "IMAGE_BACKGROUND"}


def draw_export(layout, st):
    col = layout.column()
    col.use_property_split = True
    col.use_property_decorate = False
    col.prop(st, "export_content")
    lines = st.export_content != "PRINT" or st.line_style != "NONE"
    art = st.export_content in ("PRINT", "ART_CUT")
    if art:
        col.prop(st, "line_style")
    if not art or st.line_style == "CUSTOM":
        col.prop(st, "line_color")
        col.prop(st, "line_opacity")
    sub = col.column()
    sub.active = lines
    sub.prop(st, "line_width")
    if st.export_content != "ART_CUT":
        sub.prop(st, "dashed_folds")
    if art:
        col.separator()
        col.prop(st, "tab_fill")
        if st.tab_fill:
            col.prop(st, "tab_color")
        col.prop(st, "bleed")
        col.prop(st, "export_art")
        col.prop(st, "export_sketch")
        if st.export_content == "PRINT":
            col.prop(st, "export_guides")
            sub = col.column()
            sub.active = st.export_guides
            sub.prop(st, "export_reverse")
            col.prop(st, "export_layout")
            col.prop(st, "export_labels")
    col.prop(st, "paper", text="Piece Paper")


class POPUP_UL_mechs(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_prop, index=0):
        layout.prop(item, "label", text="", emboss=False, icon=KIND_ICON[item.kind])


class POPUP_MT_add(bpy.types.Menu):
    bl_label = "Add Mechanism"
    bl_idname = "POPUP_MT_add"

    def draw(self, context):
        for k, name in (("VFOLD", "V-fold"), ("MOUTH", "Mouth (cut in)"),
                        ("BOX", "Box Fold (glued strip)"),
                        ("BOXCUT", "Box Layer (cut in)"),
                        ("CUBE", "Cube (180°)"), ("FLAP", "Pull-tab Flap"),
                        ("TUBE", "Tube (parallel strips)"), ("TETHER", "Tether"),
                        ("PYRAMID", "Pyramid / Tent (parallel strips)")):
            self.layout.operator("popup.add", text=name, icon=KIND_ICON[k]).kind = k
        st = context.scene.popup
        if st.stage_master is None:
            self.layout.operator("popup.add", text="Stage Set (V-fold)",
                                 icon=KIND_ICON["STAGE"]).kind = "STAGE"
        if st.stage_master is not None:
            self.layout.separator()
            self.layout.label(text="Stage:")
            for k, name in (("FRAME", "Frame"), ("FLOOR", "Floor"), ("CEILING", "Ceiling")):
                self.layout.operator("popup.add", text=name, icon=KIND_ICON[k]).kind = k
        if st.mechs and st.active < len(st.mechs) and \
                st.mechs[st.active].kind in ("FLOOR", "CEILING"):
            h = st.mechs[st.active]
            self.layout.separator()
            self.layout.label(text=f"In the corners of {h.label}:")
            for k, name in (("BOX", "Glued Box"), ("VFOLD", "V-fold"), ("CUBE", "Cube")):
                for side, wall in (("L", "left wall"), ("R", "right wall")):
                    op = self.layout.operator("popup.add", text=f"{name}, {wall}",
                                              icon=KIND_ICON[k])
                    op.kind, op.host, op.side = k, h.uid, side
        elif st.mechs and st.active < len(st.mechs) and st.mechs[st.active].kind == "STAGE":
            h = st.mechs[st.active]
            self.layout.separator()
            self.layout.label(text=f"In {h.label}:")
            for k, name in (("FRAME", "Frame"), ("CEILING", "Ceiling")):
                op = self.layout.operator("popup.add", text=name, icon=KIND_ICON[k])
                op.kind, op.host = k, h.uid
        if st.mechs and st.active < len(st.mechs):
            h = st.mechs[st.active]
            if h.kind in ("BOX", "BOXCUT"):
                self.layout.separator()
                self.layout.label(text=f"On {h.label}:")
                for kind, fold, text in (("BOXCUT", "C", "Inset Box Layer"),
                                         ("BOXCUT", "A", "Box Layer on Top"),
                                         ("BOXCUT", "B", "Box Layer in Front"),
                                         ("BOX", "A", "Glued Box on Top"),
                                         ("BOX", "B", "Glued Box in Front")):
                    if kind == "BOXCUT" and h.kind == "BOX" and fold != "C":
                        continue  # cut-ins need one piece of paper across the fold
                    op = self.layout.operator("popup.add", text=text, icon=KIND_ICON[kind])
                    op.kind, op.host, op.fold = kind, h.uid, fold


class _Base:
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Pop-Up"


class POPUP_PT_card(_Base, bpy.types.Panel):
    bl_label = "Pop-Up Pro"

    def draw(self, context):
        st = context.scene.popup
        if st.is_carousel:
            self.draw_carousel(context, st)
            return
        if st.stage_master is not None:
            self.draw_stage(context, st)
            return
        col = self.layout.column()
        col.use_property_split = True
        col.use_property_decorate = False
        col.prop(st, "size")
        if st.size == "CUSTOM":
            col.prop(st, "page_depth")
            col.prop(st, "spine_length")
        col.prop(st, "hold")
        row = self.layout.row(align=True)
        row.scale_y = 1.3
        row.operator("popup.build", text="Build Card" if st.rig is None else "Rebuild",
                     icon="FILE_REFRESH" if st.rig else "ADD")
        row.prop(st, "live", text="", icon="AUTO")
        if st.status:
            self.layout.label(text=st.status, icon="ERROR" if st.edited else "INFO")
        rig = st.rig
        if rig is not None and "pop_open" in rig:
            box = self.layout.box()
            box.prop(rig, '["pop_open"]', text="Open", slider=True)
            row = box.row(align=True)
            for a in (0, 45, 90, 135, 180):
                row.operator("popup.set_open", text=f"{a}°").angle = a
            row = box.row(align=True)
            row.operator("popup.animate", icon="PLAY").mode = "CYCLE"
            row.prop(st, "anim_frames", text="")
            col = box.column()
            col.use_property_split = True
            col.use_property_decorate = False
            col.prop(st, "paper_thickness")
            col.prop(st, "keep_open")
            col.prop(st, "solid_paper")
            if st.keep_open and "pop_close" in rig:
                col.label(text=f"Closes to {rig['pop_close']:.1f}°", icon="INFO")
        if st.rig is None:
            self.layout.separator()
            self.layout.operator("popup.make_carousel", icon="MESH_CIRCLE")

    def _open(self, lay, master, full):
        from . import carousel
        c = carousel.ctrl(master)
        box = lay.box()
        if c is None or carousel.OPEN not in c:
            box.label(text="Rebuild the carousel", icon="ERROR")
            return box
        box.prop(c, f'["{carousel.OPEN}"]', text="Carousel Open", slider=True)
        row = box.row(align=True)
        for a in (0, 90, 180, 270, 360):
            row.operator("popup.set_open", text=f"{a}°").angle = a
        row = box.row(align=True)
        row.operator("popup.animate", icon="PLAY").mode = "CYCLE"
        row.prop(master.popup, "anim_frames", text="")
        return box

    def draw_carousel(self, context, st):
        lay = self.layout
        col = lay.column()
        col.use_property_split = True
        col.use_property_decorate = False
        col.prop(st, "size", text="Stage Size")
        if st.size == "CUSTOM":
            col.prop(st, "page_depth")
            col.prop(st, "spine_length", text="Height")
        col.prop(st, "stage_count")
        col.label(text=f"Each stage opens to {360.0 / st.stage_count:.1f}°", icon="INFO")
        col.prop(st, "join")
        row = lay.row(align=True)
        row.operator("popup.carousel_sync", icon="FILE_REFRESH")
        row.operator("popup.export_carousel", text="Export", icon="EXPORT")
        self._open(lay, context.scene, 360.0)
        box = lay.box()
        box.label(text="Stages")
        for i, r in enumerate(st.stages):
            if r.scene is None:
                continue
            row = box.row(align=True)
            warn = r.scene.popup.warnings
            row.label(text=f"{i + 1}. {r.scene.name}", icon="ERROR" if warn else "SCENE_DATA")
            row.operator("popup.goto_stage", text="Edit", icon="RIGHTARROW").index = i + 1

    def draw_stage(self, context, st):
        lay = self.layout
        master = st.stage_master
        row = lay.row(align=True)
        row.label(text=f"Stage {st.stage_index} of {master.name}", icon="SCENE_DATA")
        row.operator("popup.goto_stage", text="Carousel", icon="MESH_CIRCLE").index = 0
        row = lay.row(align=True)
        n = len(master.popup.stages)
        if st.stage_index > 1:
            row.operator("popup.goto_stage", text="Previous", icon="TRIA_LEFT").index = \
                st.stage_index - 1
        if st.stage_index < n:
            row.operator("popup.goto_stage", text="Next", icon="TRIA_RIGHT").index = \
                st.stage_index + 1
        lay.label(text=f"Opens to {360.0 / master.popup.stage_count:.1f}°; size from the "
                       f"carousel", icon="INFO")
        row = lay.row(align=True)
        row.scale_y = 1.3
        row.operator("popup.build", text="Rebuild", icon="FILE_REFRESH")
        row.prop(st, "live", text="", icon="AUTO")
        if st.status:
            lay.label(text=st.status, icon="ERROR" if st.edited else "INFO")
        box = self._open(lay, master, 360.0)
        col = box.column()
        col.use_property_split = True
        col.use_property_decorate = False
        col.prop(st, "paper_thickness")
        col.prop(st, "solid_paper")


class POPUP_PT_mechs(_Base, bpy.types.Panel):
    bl_label = "Mechanisms"

    @classmethod
    def poll(cls, context):
        return not context.scene.popup.is_carousel

    def draw(self, context):
        st = context.scene.popup
        lay = self.layout
        row = lay.row()
        row.template_list("POPUP_UL_mechs", "", st, "mechs", st, "active", rows=3)
        col = row.column(align=True)
        col.menu("POPUP_MT_add", text="", icon="ADD")
        col.operator("popup.remove", text="", icon="REMOVE")
        if not st.mechs or st.active >= len(st.mechs):
            return
        m = st.mechs[st.active]
        col = lay.column()
        col.use_property_split = True
        col.use_property_decorate = False
        col.prop(m, "kind", text="Type")
        if m.kind == "FLAP":
            self.draw_flap(context, col, m)
            return
        if m.kind == "TUBE":
            col.prop(m, "y", text="Position")
            col.prop(m, "x", text="Strip Distance")
            col.prop(m, "depth", text="Side Length")
            col.prop(m, "height")
            col.prop(m, "front")
            col.prop(m, "front_style")
            col.prop(m, "back")
            col.prop(m, "back_style")
            col.prop(m, "tab")
            col.prop(m, "tab_side", text="Base Tabs")
            col.prop(m, "roof")
            if m.roof == "POINTED":
                col.prop(m, "roof_height")
                col.prop(m, "ridge")
            elif m.roof == "FLAT":
                col.prop(m, "roof_fold")
                col.prop(m, "eave")
                if m.roof_fold == "DIP":
                    col.prop(m, "rib")
            self.draw_warnings(context, m)
            return
        if m.kind == "STAGE":
            col.prop(m, "y", text="Position")
            col.prop(m, "phi_l", text="Glue Angle")
            col.label(text=f"Opens to {2 * m.phi_l:.0f}° when the card is flat", icon="INFO")
            col.prop(m, "glue", text="Half Width")
            col.prop(m, "height")
            col.prop(m, "tab")
            col.prop(m, "tab_side")
            self.draw_warnings(context, m)
            return
        if m.kind == "FRAME":
            import math as _m
            master = st.stage_master
            tmax = 360.0 / master.popup.stage_count if master else 180.0
            host = next((h for h in st.mechs if h.uid == m.host_uid), None)
            if host is not None and host.kind == "STAGE":
                tmax = 2 * host.phi_l
                col.prop(m, "host", text="Stage")
            col.prop(m, "x", text="Depth")
            col.prop(m, "y", text="Bottom")
            col.prop(m, "height")
            col.prop(m, "tab")
            col.label(text=f"Width {2 * m.x * _m.sin(_m.radians(tmax / 2)):.1f} mm "
                           f"(flat at {tmax:.0f}°)", icon="INFO")
            self.draw_warnings(context, m)
            return
        if m.kind in ("FLOOR", "CEILING"):
            if st.stage_master is None:
                col.prop(m, "host", text="Stage")
            col.prop(m, "depth")
            col.prop(m, "lead")
            col.prop(m, "tab")
            self.draw_warnings(context, m)
            return
        if m.kind == "PYRAMID":
            col.prop(m, "y", text="Position")
            col.prop(m, "x", text="Strip Distance")
            col.prop(m, "depth", text="Base Length")
            col.prop(m, "height")
            col.prop(m, "ridge")
            col.prop(m, "front", text="Front Width")
            col.prop(m, "front_style")
            col.prop(m, "back", text="Back Width")
            col.prop(m, "back_style")
            col.prop(m, "tab")
            col.prop(m, "tab_side", text="Base Tabs")
            self.draw_warnings(context, m)
            return
        if m.kind == "TETHER":
            col.prop(m, "from_tube")
            col.prop(m, "from_pt")
            col.prop(m, "to")
            if m.to == "TUBE":
                col.prop(m, "to_tube")
                col.prop(m, "to_pt")
            else:
                col.prop(m, "to_y")
                col.prop(m, "tab_side", text="Foot Tab")
            col.prop(m, "height")
            col.prop(m, "bend")
            col.prop(m, "slack")
            col.prop(m, "tab")
            self.draw_warnings(context, m)
            return
        col.prop(m, "host")
        hm = next((h for h in st.mechs if h.uid == m.host_uid), None) if m.host_uid else None
        if hm is not None and hm.kind in ("BOX", "BOXCUT"):
            col.prop(m, "fold")
        joint = hm is not None and hm.kind in ("FLOOR", "CEILING")
        if joint:
            col.prop(m, "side", text="Wall")
        col.prop(m, "y", text={"MOUTH": "Slit Position"}.get(m.kind, "Position")
                 if not joint else "Out from Fold")
        if m.kind == "CUBE":
            col.prop(m, "size")
            col.prop(m, "height")
            col.prop(m, "lid")
            col.prop(m, "tab")
            col.prop(m, "tab_side", text="Base Tabs")
        elif m.kind == "MOUTH":
            col.prop(m, "jaw")
            col.prop(m, "upper")
            col.prop(m, "lower")
        elif m.kind == "VFOLD":
            col.prop(m, "shape")
            col.prop(m, "height", text="Fold Length")
            col.prop(m, "glue")
            col.prop(m, "symmetric")
            col.prop(m, "phi_l", text="Glue Angle" if m.symmetric else "Glue Angle L")
            if not m.symmetric:
                col.prop(m, "phi_r")
            col.prop(m, "alpha_l", text="Piece Angle" if m.symmetric else "Piece Angle L")
            if not m.symmetric:
                col.prop(m, "alpha_r")
            col.prop(m, "tab")
            col.prop(m, "tab_side")
        else:
            col.prop(m, "width", text="Height")
            if joint:
                # which side of the joint each width lies on
                flat = "Along Floor" if hm.kind == "FLOOR" else "Along Ceiling"
                wall_first = (hm.kind == "FLOOR") == (m.side == "R")
                left, right = ("Up Wall", flat) if wall_first else (flat, "Up Wall")
                if hm.kind == "CEILING":
                    left = left.replace("Up Wall", "Down Wall")
                    right = right.replace("Up Wall", "Down Wall")
            else:
                left, right = "Width Left", "Width Right"
            col.prop(m, "height", text=left)
            col.prop(m, "depth", text=right)
            if m.kind == "BOX":
                col.prop(m, "tab")
        self.draw_warnings(context, m)


def _draw_flap(self, context, col, m):
    st = context.scene.popup
    col.prop(m, "side")
    col.prop(m, "x")
    col.prop(m, "y", text="Up the Page")
    col.prop(m, "hinge")
    col.prop(m, "width")
    col.prop(m, "length")
    col.prop(m, "tab", text="Hinge Tab")
    col.separator()
    col.prop(m, "angle")
    col.prop(m, "glue_at")
    col.prop(m, "strip")
    col.prop(m, "gap")
    col.prop(m, "pull_out")
    rig = st.rig
    name = f"pop_pull_{m.uid}"
    if rig is not None and name in rig:
        box = col.box()
        box.prop(rig, f'["{name}"]', text="Pull", slider=True)
        box.operator("popup.animate_pull", icon="PLAY").uid = m.uid
    self.draw_warnings(context, m)


def _draw_warnings(self, context, m):
    ws = [w for w in context.scene.popup.warnings.splitlines()
          if w.startswith(m.label + ":") or w.startswith(m.label + " and")]
    if ws:
        box = self.layout.box()
        for w in ws:
            box.label(text=w[len(m.label) + 1:].strip() if w.startswith(m.label + ":") else w,
                      icon="ERROR")


POPUP_PT_mechs.draw_flap = _draw_flap
POPUP_PT_mechs.draw_warnings = _draw_warnings


class POPUP_UL_openings(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_prop, index=0):
        ic = {"RECT": "MESH_PLANE", "ARCH": "MESH_CAPSULE", "OVAL": "MESH_CIRCLE"}[item.shape]
        layout.prop(item, "label", text="", emboss=False, icon=ic)


class POPUP_PT_openings(_Base, bpy.types.Panel):
    bl_label = "Openings and Holes"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        return context.scene.popup.rig is not None

    def draw(self, context):
        st = context.scene.popup
        lay = self.layout
        row = lay.row()
        row.template_list("POPUP_UL_openings", "", st, "openings", st, "active_opening", rows=3)
        col = row.column(align=True)
        col.operator("popup.add_opening", text="", icon="ADD")
        col.operator("popup.remove_opening", text="", icon="REMOVE")
        if 0 <= st.active_opening < len(st.openings):
            o = st.openings[st.active_opening]
            col = lay.column()
            col.use_property_split = True
            col.use_property_decorate = False
            col.prop(o, "on")
            col.prop(o, "shape")
            col.prop(o, "x")
            col.prop(o, "y")
            col.prop(o, "width")
            col.prop(o, "height")
            col.prop(o, "through")
            if o.through == "NEXT" and (st.stage_master is None or o.on_uid != 0):
                col.label(text="Next Stage works on a carousel stage's background",
                          icon="ERROR")
        box = lay.box()
        box.label(text="Painted holes: paint with Erase Alpha, then", icon="BRUSH_DATA")
        row = box.row(align=True)
        row.operator("popup.trace_holes", icon="MOD_BOOLEAN")
        row.operator("popup.trace_holes", text="", icon="X").clear = True
        box = lay.box()
        box.label(text="Drawn holes: closed strokes on the flat layout", icon="GREASEPENCIL")
        box.operator("popup.draw_holes", icon="MOD_BOOLEAN")
        row = box.row(align=True)
        row.operator("popup.build", text="Cut", icon="FILE_REFRESH")
        row.operator("popup.keep_holes", text="Keep", icon="CHECKMARK").edit = False
        row.operator("popup.keep_holes", text="Edit", icon="GREASEPENCIL").edit = True


class POPUP_PT_checks(_Base, bpy.types.Panel):
    bl_label = "Checks"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        return context.scene.popup.rig is not None

    def draw_header(self, context):
        n = len(context.scene.popup.warnings.splitlines())
        self.layout.label(text="", icon="ERROR" if n else "CHECKMARK")

    def draw(self, context):
        ws = context.scene.popup.warnings.splitlines()
        if not ws:
            self.layout.label(text="Folds flat, opens flat, no collisions found")
        col = self.layout.column(align=True)
        for w in ws:
            col.label(text=w, icon="ERROR")


class POPUP_PT_art(_Base, bpy.types.Panel):
    bl_label = "Artwork"

    @classmethod
    def poll(cls, context):
        return context.scene.popup.rig is not None

    def draw(self, context):
        st = context.scene.popup
        lay = self.layout
        col = lay.column(align=True)
        col.label(text="Paint (Texture Paint / Paint System)")
        if bpy.data.images.get(N(context.scene, "Pop-up Art")) is None:
            col.operator("popup.add_art", icon="TEXTURE")
        row = col.row(align=True)
        row.operator("popup.paint", text="Paint Flat", icon="BRUSH_DATA").target = "LAYOUT"
        row.operator("popup.paint", text="Paint Folded", icon="BRUSH_DATA").target = "CARD"
        col = lay.column(align=True)
        col.label(text="Sketch (Grease Pencil)")
        col.prop(st, "sketch_panel", text="")
        col.operator("popup.sketch", icon="GREASEPENCIL").panel = ""
        col = lay.column(align=True)
        col.label(text="Print")
        col.operator("popup.view_layout", icon="VIEW_ORTHO")
        col.operator("popup.bake", icon="RENDER_STILL")


class POPUP_PT_export(_Base, bpy.types.Panel):
    bl_label = "Export"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        return context.scene.popup.rig is not None

    def draw(self, context):
        draw_export(self.layout, context.scene.popup)
        self.layout.operator("popup.export_svg", icon="EXPORT")


classes = (POPUP_UL_mechs, POPUP_UL_openings, POPUP_MT_add, POPUP_PT_card, POPUP_PT_mechs,
           POPUP_PT_openings, POPUP_PT_checks,
           POPUP_PT_art, POPUP_PT_export)


def register():
    for c in classes:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
