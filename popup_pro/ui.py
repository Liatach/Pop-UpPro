import bpy

from . import live

KIND_ICON = {"VFOLD": "MOD_TRIANGULATE", "BOX": "MESH_CUBE", "BOXCUT": "SNAP_FACE",
             "MOUTH": "MOD_SIMPLEDEFORM", "CUBE": "CUBE", "FLAP": "MOD_CLOTH",
             "TUBE": "MESH_CYLINDER", "TETHER": "LINKED",
             "PYRAMID": "CONE"}


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


class POPUP_PT_mechs(_Base, bpy.types.Panel):
    bl_label = "Mechanisms"

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
        col.prop(m, "y", text={"MOUTH": "Slit Position"}.get(m.kind, "Position"))
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
            col.prop(m, "height", text="Width Left")
            col.prop(m, "depth", text="Width Right")
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
        if bpy.data.images.get("Pop-up Art") is None:
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


classes = (POPUP_UL_mechs, POPUP_MT_add, POPUP_PT_card, POPUP_PT_mechs, POPUP_PT_checks,
           POPUP_PT_art, POPUP_PT_export)


def register():
    for c in classes:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
