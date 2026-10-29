import bpy

from . import live
from .naming import N

KIND_ICON = {"VFOLD": "MOD_TRIANGULATE", "BOX": "MESH_CUBE", "BOXCUT": "SNAP_FACE",
             "MOUTH": "MOD_SIMPLEDEFORM", "CUBE": "CUBE", "FLAP": "MOD_CLOTH",
             "TUBE": "MESH_CYLINDER", "TETHER": "LINKED",
             "PYRAMID": "CONE", "FRAME": "IMAGE_PLANE", "FLOOR": "TRIA_DOWN_BAR",
             "CEILING": "TRIA_UP_BAR", "STAGE": "IMAGE_BACKGROUND",
             "STANDUP": "OUTLINER_OB_IMAGE", "ROOF": "HOME"}


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
                        ("PYRAMID", "Pyramid / Tent (parallel strips)"),
                        ("STANDUP", "Stand-up (parallelogram)")):
            self.layout.operator("popup.add", text=name, icon=KIND_ICON[k]).kind = k
            if k == "VFOLD":
                op = self.layout.operator("popup.add", text="V-fold (asymmetric)",
                                          icon=KIND_ICON[k])
                op.kind, op.variant = "VFOLD", "ASYM"
            if k == "BOX":
                op = self.layout.operator("popup.add", text="Strap (off-centre gullies)",
                                          icon=KIND_ICON[k])
                op.kind, op.variant = "BOX", "STRAP"
        st = context.scene.popup
        if st.stage_master is None:
            self.layout.operator("popup.add", text="Stage Set (V-fold)",
                                 icon=KIND_ICON["STAGE"]).kind = "STAGE"
        if st.stage_master is not None:
            self.layout.separator()
            self.layout.label(text="Stage:")
            for k, name in (("FRAME", "Frame"), ("FLOOR", "Floor"), ("CEILING", "Ceiling")):
                self.layout.operator("popup.add", text=name, icon=KIND_ICON[k]).kind = k
        if st.stage_master is None:
            self.layout.separator()
        self.layout.operator("popup.add", text="Roof (peaked, cuts a gable)",
                             icon=KIND_ICON["ROOF"]).kind = "ROOF"
        op = self.layout.operator("popup.add", text="Valley Floor (roof upside down)",
                                  icon=KIND_ICON["ROOF"])
        op.kind, op.variant = "ROOF", "VALLEY"
        if st.mechs and st.active < len(st.mechs) and \
                st.mechs[st.active].kind in ("FLOOR", "CEILING"):
            h = st.mechs[st.active]
            self.layout.separator()
            self.layout.label(text=f"In the corners of {h.label}:")
            for k, name in (("BOX", "Box Fold"), ("VFOLD", "V-fold"), ("CUBE", "Cube")):
                for side, wall in (("L", "left wall"), ("R", "right wall")):
                    op = self.layout.operator("popup.add", text=f"{name}, {wall}",
                                              icon=KIND_ICON[k])
                    op.kind, op.host, op.side = k, h.uid, side
            op = self.layout.operator("popup.add", text="V-fold on its crease",
                                      icon=KIND_ICON["VFOLD"])
            op.kind, op.host, op.fold = "VFOLD", h.uid, "V"
        elif st.mechs and st.active < len(st.mechs) and st.mechs[st.active].kind == "VFOLD":
            h = st.mechs[st.active]
            self.layout.separator()
            self.layout.label(text=f"On {h.label}:")
            for kind, text in (("BOX", "Box Fold on the Crease"),
                               ("BOXCUT", "Box Layer cut in the Crease"),
                               ("VFOLD", "V-fold on the Crease"),
                               ("MOUTH", "Mouth cut in the Crease"),
                               ("STANDUP", "Stand-up on the Crease")):
                op = self.layout.operator("popup.add", text=text, icon=KIND_ICON[kind])
                op.kind, op.host, op.fold = kind, h.uid, "V"
            for kind, text in (("CUBE", "Cube in the V (on the Crease)"),
                               ("TUBE", "Tube in the V (on the Crease)")):
                op = self.layout.operator("popup.add", text=text, icon=KIND_ICON[kind])
                op.kind, op.host, op.fold = kind, h.uid, "V"
            self.layout.label(text="On its glue folds (off-centre):")
            for fold, where in (("FL", "in front, left"), ("FR", "in front, right"),
                                ("BL", "behind, left"), ("BR", "behind, right")):
                for kind, name in (("STANDUP", "Stand-up"), ("CUBE", "Cube"),
                                   ("TUBE", "Tube"), ("VFOLD", "V-fold"),
                                   ("BOX", "Box Fold")):
                    if fold[0] == "B" and kind != "STANDUP":
                        continue  # inside the V there's little room: stand-ups only
                    op = self.layout.operator("popup.add", text=f"{name} {where}",
                                              icon=KIND_ICON[kind])
                    op.kind, op.host, op.fold = kind, h.uid, fold
        elif st.mechs and st.active < len(st.mechs) and st.mechs[st.active].kind == "STAGE":
            h = st.mechs[st.active]
            self.layout.separator()
            self.layout.label(text=f"In {h.label}:")
            for k, name in (("FRAME", "Frame"), ("CEILING", "Ceiling")):
                op = self.layout.operator("popup.add", text=name, icon=KIND_ICON[k])
                op.kind, op.host = k, h.uid
        if st.mechs and st.active < len(st.mechs) and \
                st.mechs[st.active].kind in ("CUBE", "TUBE"):
            h = st.mechs[st.active]
            self.layout.separator()
            self.layout.label(text=f"Outside the walls of {h.label}:")
            for wall, where in (("L", "left wall"), ("R", "right wall")):
                for kind, name in (("CUBE", "Cube"), ("TUBE", "Tube"), ("VFOLD", "V-fold"),
                                   ("BOX", "Box Fold"), ("STANDUP", "Stand-up")):
                    op = self.layout.operator("popup.add", text=f"{name}, {where}",
                                              icon=KIND_ICON[kind])
                    op.kind, op.host, op.fold = kind, h.uid, "W" + wall
        if st.mechs and st.active < len(st.mechs):
            h = st.mechs[st.active]
            if h.kind in ("BOX", "BOXCUT", "STANDUP"):
                self.layout.separator()
                self.layout.label(text=f"On {h.label}:")
                for kind, fold, text in (("BOXCUT", "C", "Inset Box Layer"),
                                         ("BOXCUT", "A", "Box Layer on Top"),
                                         ("BOXCUT", "B", "Box Layer in Front"),
                                         ("BOX", "A", "Box Fold on Top"),
                                         ("BOX", "B", "Box Fold in Front"),
                                         ("STANDUP", "A", "Stand-up on Top"),
                                         ("STANDUP", "B", "Stand-up in Front"),
                                         ("CUBE", "A", "Cube on Top"),
                                         ("CUBE", "B", "Cube in Front"),
                                         ("TUBE", "A", "Tube on Top"),
                                         ("TUBE", "B", "Tube in Front"),
                                         ("VFOLD", "A", "V-fold on Top"),
                                         ("VFOLD", "B", "V-fold in Front")):
                    if kind == "BOXCUT" and h.kind != "BOXCUT" and fold != "C":
                        continue  # cut-ins need one piece of paper across the fold
                    if kind == "BOXCUT" and h.kind == "STANDUP":
                        continue  # cut-ins need one piece of paper across the fold
                    op = self.layout.operator("popup.add", text=text, icon=KIND_ICON[kind])
                    op.kind, op.host, op.fold = kind, h.uid, fold
                if h.kind == "BOX" and h.peaks > 1:
                    for kind, name in (("CUBE", "Cube"), ("TUBE", "Tube"), ("VFOLD", "V-fold"),
                                       ("STANDUP", "Stand-up")):
                        op = self.layout.operator("popup.add", text=f"{name} in a Valley",
                                                  icon=KIND_ICON[kind])
                        op.kind, op.host, op.fold = kind, h.uid, "VAL"


def draw_anim(box, sc, st, to):
    """Movement test: a play button; its settings folded away beneath."""
    from .ops import anim_timing
    head, body = box.panel("popup_anim", default_closed=True)
    playing = bpy.context.screen is not None and bpy.context.screen.is_animation_playing
    head.operator("screen.animation_play", text="", icon="PAUSE" if playing else "PLAY")
    head.label(text="Movement Test")
    try:
        n_open, n_hold, n_close = anim_timing(sc)
        head.label(text=f"{n_open + n_hold + n_close} frames")
    except Exception:
        pass
    if body is None:
        return
    sub = body
    col = sub.column(align=True)
    col.use_property_split = True
    col.use_property_decorate = False
    col.prop(st, to)
    col.prop(st, "anim_open")
    col.prop(st, "anim_hold")
    col.prop(st, "anim_close")
    try:
        n_open, n_hold, n_close = anim_timing(sc)
        sub.label(text=f"{n_open} + {n_hold} + {n_close} frames at "
                  f"{sc.render.fps / (sc.render.fps_base or 1.0):g} fps", icon="TIME")
    except Exception:
        pass
    row = sub.row(align=True)
    row.operator("popup.animate", text="Open", icon="PLAY").mode = "OPEN"
    row.operator("popup.animate", text="Open and Close", icon="FILE_REFRESH").mode = "CYCLE"


def _tabs(lay, m, side=True, side_text="Tab Side"):
    """Glue tabs, tucked away: the size in the header, the rest inside."""
    head, body = lay.panel(f"popup_tabs_{m.kind}", default_closed=True)
    head.label(text="Glue Tabs")
    head.prop(m, "tab", text="")
    if body is not None and side:
        c = body.column()
        c.use_property_split = True
        c.use_property_decorate = False
        c.prop(m, "tab_side", text=side_text)


def _where(col, st, m):
    """Where a mechanism stands: the same few words for every kind."""
    col.prop(m, "host", text="Stands On")
    hm = next((h for h in st.mechs if h.uid == m.host_uid), None) if m.host_uid else None
    if hm is not None and hm.kind in ("BOX", "BOXCUT", "STANDUP"):
        col.prop(m, "fold", text="Fold")
        if hm.kind == "BOX" and m.fold == "V":
            col.prop(m, "gully")
    if hm is not None and hm.kind == "VFOLD":
        col.prop(m, "vside", text="Fold")
    if hm is not None and hm.kind in ("CUBE", "TUBE"):
        col.prop(m, "wall", text="Fold")
    return hm


def _paper(box, st, rig):
    """Paper thickness and how it shows, folded away: the thickness in view."""
    head, body = box.panel("popup_paper", default_closed=True)
    head.label(text="Paper")
    head.prop(st, "paper_thickness", text="")
    if body is None:
        return
    col = body.column()
    col.use_property_split = True
    col.use_property_decorate = False
    if rig is not None:
        col.prop(st, "keep_open")
    col.prop(st, "solid_paper")
    if rig is not None and st.keep_open and "pop_close" in rig:
        col.label(text=f"Closes to {rig['pop_close']:.1f}°", icon="INFO")


class _Base:
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Pop-Up"


class POPUP_PT_card(_Base, bpy.types.Panel):
    bl_label = "Pop-Up Pro"
    bl_order = 0

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
            draw_anim(box, context.scene, st, "anim_to")
            _paper(box, st, rig)
        if st.rig is None:
            self.layout.separator()
            self.layout.operator("popup.make_carousel", icon="MESH_CIRCLE")
        row = self.layout.row(align=True)
        row.operator("popup.setup_scene", icon="SHADING_RENDERED")
        row.prop(st, "render_look", text="", icon="LIGHT_SUN")

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
        draw_anim(box, master, master.popup, "anim_to_carousel")
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
        row = lay.row(align=True)
        row.operator("popup.setup_scene", icon="SHADING_RENDERED")
        row.prop(st, "render_look", text="", icon="LIGHT_SUN")
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
        _paper(box, st, None)


class POPUP_PT_mechs(_Base, bpy.types.Panel):
    bl_label = "Mechanisms"
    bl_order = 2

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
        col.operator("popup.duplicate", text="", icon="DUPLICATE")
        col.separator()
        col.prop(st, "highlight", text="", icon="RESTRICT_SELECT_OFF")
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
            _where(col, st, m)
            col.prop(m, "y", text="Position")
            col.prop(m, "x", text="Strip Distance")
            col.prop(m, "depth", text="Length Along Fold")
            col.prop(m, "height")
            col.prop(m, "front")
            col.prop(m, "front_style")
            col.prop(m, "back")
            col.prop(m, "back_style")
            col.prop(m, "roof")
            if m.roof == "POINTED":
                col.prop(m, "roof_height")
                col.prop(m, "ridge")
            elif m.roof == "FLAT":
                col.prop(m, "roof_fold")
                col.prop(m, "eave")
                if m.roof_fold == "DIP":
                    col.prop(m, "rib")
            _tabs(self.layout, m)
            self.draw_warnings(context, m)
            return
        if m.kind == "STAGE":
            col.prop(m, "y", text="Position")
            col.prop(m, "phi_l", text="Glue Angle")
            col.label(text=f"Opens to {2 * m.phi_l:.0f}° when the card is flat", icon="INFO")
            col.prop(m, "glue", text="Glue Length (half width)")
            col.prop(m, "height")
            _tabs(self.layout, m)
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
            col.label(text=f"Width {2 * m.x * _m.sin(_m.radians(tmax / 2)):.1f} mm "
                           f"(flat at {tmax:.0f}°)", icon="INFO")
            _tabs(self.layout, m, side=False)
            self.draw_warnings(context, m)
            return
        if m.kind in ("FLOOR", "CEILING"):
            if st.stage_master is None:
                col.prop(m, "host", text="Stage")
            col.prop(m, "depth")
            col.prop(m, "lead")
            _tabs(self.layout, m, side=False)
            self.draw_warnings(context, m)
            return
        if m.kind == "PYRAMID":
            col.prop(m, "y", text="Position")
            col.prop(m, "x", text="Strip Distance")
            col.prop(m, "depth", text="Length Along Fold")
            col.prop(m, "height")
            col.prop(m, "ridge")
            col.prop(m, "front", text="Front Width")
            col.prop(m, "front_style")
            col.prop(m, "back", text="Back Width")
            col.prop(m, "back_style")
            _tabs(self.layout, m)
            self.draw_warnings(context, m)
            return
        if m.kind == "ROOF":
            v = m.valley
            info = {}
            if st.rig is not None:
                try:
                    import json
                    info = json.loads(st.rig.get("pop_meta", "{}")).get("roofs", {}).get(
                        str(m.uid), {})
                except (ValueError, TypeError, AttributeError):
                    info = {}
            col.prop(m, "valley")
            col.prop(m, "y", text="Position")
            col.prop(m, "phi_l", text="Glue Angle (slope)")
            row = col.row()
            row.prop(m, "glue", text="Glue Length (eaves)")
            if info and info.get("eaves", 0) < m.glue - 0.05:
                c = col.column()
                c.scale_y = 0.7
                c.label(text=f"    reaches the card's edge at {info['eaves']:.0f} mm",
                        icon="INFO")
            col.prop(m, "height", text="Fold Length (valley)" if v else "Fold Length (ridge)")
            if info and info.get("fit", 1e9) < 1e8:
                c = col.column()
                c.scale_y = 0.7
                c.label(text=f"    fits the shut card up to {info['fit']:.0f} mm",
                        icon="ERROR" if m.height > info["fit"] + 0.05 else "INFO")
            col.prop(m, "level", text="Level Valley" if v else "Level Ridge")
            sub = col.row()
            if m.level:
                sub.label(text=f"Piece Angle: {info['alpha']:.1f}° (set for level)"
                          if info else "Piece Angle: set for level")
            else:
                sub.prop(m, "alpha_l", text="Piece Angle")
            col.label(text="Cuts the background away " + ("below the glue lines"
                      if v else "to a gable along the eaves"), icon="INFO")
            _tabs(self.layout, m, side=False)
            _draw_lines(self.layout, context, m)
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
            col.prop(m, "height")
            col.prop(m, "bend")
            col.prop(m, "slack")
            _tabs(self.layout, m, side=m.to != "TUBE", side_text="Foot Tab Side")
            self.draw_warnings(context, m)
            return
        hm = _where(col, st, m)
        joint = hm is not None and hm.kind in ("FLOOR", "CEILING")
        if joint and m.kind == "VFOLD":
            col.prop(m, "on_crease")
        if joint and not (m.kind == "VFOLD" and m.on_crease):
            col.prop(m, "side", text="Wall")
        col.prop(m, "y", text="Position")
        if m.kind == "CUBE":
            col.prop(m, "size", text="Width" if m.size_r <= 0 else "Width Left")
            col.prop(m, "size_r", text="Width Right (0 = square)" if m.size_r <= 0
                     else "Width Right")
            col.prop(m, "height")
            row = col.row()
            row.active = m.size_r <= 0 or abs(m.size_r - m.size) < 1e-6
            row.prop(m, "lid")
        elif m.kind == "MOUTH":
            col.prop(m, "jaw")
            col.prop(m, "upper")
            col.prop(m, "lower")
        elif m.kind == "STANDUP":
            flat = m.stand == "FLAT"
            col.prop(m, "stand")
            col.prop(m, "width", text="Leg Width" if flat else "Bridge Width")
            col.prop(m, "height", text="Height Above Floor" if flat else "Bridge Height")
            col.prop(m, "depth", text="Leg Out From Back" if flat else "Out From Back")
            col.prop(m, "img_w")
            col.prop(m, "img_h", text="Picture Depth" if flat else "Picture Height")
            col.label(text="Shape the picture by erasing its art (Holes and Shaping)",
                      icon="INFO")
        elif m.kind == "VFOLD":
            col.prop(m, "shape")
            col.prop(m, "height", text="Fold Length")
            col.prop(m, "glue", text="Glue Length" if m.symmetric else "Glue Length L")
            if not m.symmetric:
                col.prop(m, "glue_r")
            col.prop(m, "symmetric")
            col.prop(m, "phi_l", text="Glue Angle" if m.symmetric else "Glue Angle L")
            if not m.symmetric:
                col.prop(m, "phi_r")
                col.prop(m, "fold_flat")
            if not m.symmetric and m.fold_flat:
                col.prop(m, "lean")
                d = m.to_dict()
                col.label(text=f"Piece angles {d['alpha_l']:.0f}° L, {d['alpha_r']:.0f}° R; "
                          f"leans {'right' if m.phi_r > m.phi_l else 'left'}", icon="INFO")
            else:
                col.prop(m, "alpha_l", text="Piece Angle" if m.symmetric else "Piece Angle L")
                if not m.symmetric:
                    col.prop(m, "alpha_r")
            if not m.host_uid:
                col.prop(m, "cut_above")
            _tabs(self.layout, m)
            _draw_lines(self.layout, context, m)
        else:
            col.prop(m, "width", text="Length Along Fold")
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
            if m.kind in ("BOX", "BOXCUT"):
                col.prop(m, "slant")
            if m.kind == "BOX":
                col.prop(m, "peaks")
        if m.kind in ("CUBE", "STANDUP", "BOX"):
            _tabs(self.layout, m, side=m.kind == "CUBE")
        if m.kind in ("BOX", "BOXCUT"):
            _draw_lines(self.layout, context, m)
        self.draw_warnings(context, m)


def _group_head(lines, item):
    """The first line of item's shape (a preset's lines collapse to it)."""
    return next((ln for ln in lines if ln.group == item.group), item)


class POPUP_UL_lines(bpy.types.UIList):
    """Lines one by one; a preset's lines (battlements, say) fold into one
    row for the whole shape, which opens to show them."""

    def filter_items(self, context, data, propname):
        lines = getattr(data, propname)
        flags = []
        for ln in lines:
            hidden = (ln.group and not ln.expanded and len(
                [x for x in lines if x.group == ln.group]) > 1 and
                _group_head(lines, ln) != ln)
            flags.append(0 if hidden else self.bitflag_filter_item)
        return flags, []

    def draw_item(self, context, layout, data, item, icon, active_data, active_prop, index=0):
        ic = {"CREASE": "MOD_LINEART", "CUT": "SCULPTMODE_HLT", "JOIN": "AUTOMERGE_ON"}[item.kind]
        row = layout.row(align=True)
        lines = data.card_lines if self.list_id == "card" else data.lines
        mates = [x for x in lines if item.group and x.group == item.group]
        if len(mates) > 1:
            if _group_head(lines, item) == item:
                row.prop(item, "expanded", text="", emboss=False,
                         icon="DISCLOSURE_TRI_DOWN" if item.expanded else "DISCLOSURE_TRI_RIGHT")
                row.label(text=f"{item.shape_name or 'Shape'} ({len(mates)} lines)",
                          icon="OUTLINER_OB_GROUP_INSTANCE")
                return
            row.separator(factor=3.0)
        kind = {"CREASE": "Crease", "CUT": "Cut", "JOIN": "Join tab"}[item.kind]
        if item.path:
            what = f"drawn {kind.lower()}"
        elif item.by_angle:
            what = f"{kind} from ({item.x0:.0f}, {item.y0:.0f}) at {item.angle:.0f}°"
        else:
            what = f"{kind} ({item.x0:.0f}, {item.y0:.0f}) to ({item.x1:.0f}, {item.y1:.0f})"
        row.label(text=what, icon=ic)
        row.prop(item, "mirror", text="", icon="MOD_MIRROR", emboss=False)


def _line_fields(c, ln):
    whole = ln.group and ln.shape_name and not ln.expanded
    if not whole:
        c.prop(ln, "kind")
        c.prop(ln, "mirror")
        c.separator()
    c.label(text="Whole shape" if ln.group else "This line", icon="ORIENTATION_GIMBAL")
    c.prop(ln, "flip")
    c.prop(ln, "turn")
    c.prop(ln, "move_x")
    c.prop(ln, "move_y")
    c.separator()
    if whole:
        c.label(text="Open the shape (triangle) to edit its lines one by one")
        return
    if ln.path:
        c.label(text="Its outline: redraw it to change the shape")
        return
    c.prop(ln, "by_angle")
    c.prop(ln, "x0")
    c.prop(ln, "y0")
    if ln.by_angle:
        c.prop(ln, "angle")
        c.prop(ln, "length")
    else:
        c.prop(ln, "x1")
        c.prop(ln, "y1")


def _draw_lines(lay, context, m):
    box = lay.box()
    box.label(text="Extra creases and cuts", icon="MOD_LINEART")
    if m.kind in ("BOX", "BOXCUT"):
        c = box.column(align=True)
        c.scale_y = 0.7
        c.label(text="Doors and windows: Holes and Shaping", icon="INFO")
        c.label(text="X: from the front's top fold (- over the top, + down the front)")
        c.label(text="Y: along from the box's end; Mirror flips end to end")
    row = box.row()
    row.template_list("POPUP_UL_lines", "", m, "lines", m, "active_line", rows=2)
    col = row.column(align=True)
    col.operator_menu_enum("popup.add_line", "preset", text="", icon="ADD")
    col.operator("popup.remove_line", text="", icon="REMOVE")
    if 0 <= m.active_line < len(m.lines):
        ln = m.lines[m.active_line]
        c = box.column(align=True)
        c.use_property_split = True
        c.use_property_decorate = False
        _line_fields(c, ln)
    row = box.row(align=True)
    row.operator("popup.draw_lines", text="Draw Creases", icon="GREASEPENCIL").kind = "CREASE"
    row.operator("popup.draw_lines", text="Draw Cuts", icon="GREASEPENCIL").kind = "CUT"
    box.operator("popup.take_lines", icon="CHECKMARK")


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
    bl_label = "Holes and Shaping"
    bl_order = 3

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
            col.prop(o, "face_pick")
            col.prop(o, "cut", expand=True)
            col.prop(o, "shape")
            if o.face:
                col.prop(o, "x", text="X (Across Face)")
                col.prop(o, "y", text="Y (Up Face)")
            else:
                col.prop(o, "x")
                col.prop(o, "y")
            col.prop(o, "width")
            col.prop(o, "height")
            col.prop(o, "turn")
            if o.cut == "DOOR":
                col.prop(o, "hinge")
                col.prop(o, "door_open")
                if o.shape == "ARCH" and o.hinge == "TOP":
                    col.label(text="An arch has no straight top: hinged on the left",
                              icon="INFO")
                if o.shape == "OVAL":
                    col.label(text="An oval door is cut as a rectangle", icon="INFO")
            else:
                col.prop(o, "through")
            if o.through == "NEXT" and (st.stage_master is None or
                                        (o.on_piece or ("Card" if not o.on_uid else "")) != "Card"):
                col.label(text="Next Stage works on a carousel stage's background",
                          icon="ERROR")
        box = lay.box()
        box.label(text="The background folds in", icon="MOD_LINEART")
        c = box.column()
        c.use_property_split = True
        c.use_property_decorate = False
        c.prop(st, "ceiling")
        if st.ceiling != "NONE":
            c.prop(st, "ceiling_drop")
            c.prop(st, "ceiling_slope")
            if st.ceiling == "PEAK":
                c.prop(st, "ceiling_lift")
        c.separator()
        c.prop(st, "floor")
        if st.floor != "NONE":
            c.prop(st, "floor_rise")
            c.prop(st, "floor_slope")
            if st.floor == "PEAK":
                c.prop(st, "floor_dip")
        head, body = box.panel("popup_card_lines", default_closed=True)
        head.label(text="Your own creases and cuts (%d)" % len(st.card_lines))
        if body is not None:
            row = body.row()
            row.template_list("POPUP_UL_lines", "card", st, "card_lines", st,
                              "active_card_line", rows=2)
            col = row.column(align=True)
            col.operator_menu_enum("popup.add_card_line", "preset", text="", icon="ADD")
            col.operator("popup.remove_card_line", text="", icon="REMOVE")
            if 0 <= st.active_card_line < len(st.card_lines):
                ln = st.card_lines[st.active_card_line]
                c = body.column(align=True)
                c.use_property_split = True
                c.use_property_decorate = False
                _line_fields(c, ln)
            row = body.row(align=True)
            row.operator("popup.draw_lines", text="Draw Creases",
                         icon="GREASEPENCIL").kind = "CREASE"
            row.operator("popup.draw_lines", text="Draw Cuts", icon="GREASEPENCIL").kind = "CUT"
            body.operator("popup.take_lines", icon="CHECKMARK")
        box = lay.box()
        box.label(text="Painted: erase alpha to cut holes or trim edges", icon="BRUSH_DATA")
        box.prop(st, "auto_holes")
        row = box.row(align=True)
        row.operator("popup.trace_holes", text="Cut Now", icon="MOD_BOOLEAN")
        row.operator("popup.trace_holes", text="", icon="X").clear = True
        box = lay.box()
        box.label(text="Drawn holes: closed strokes on the flat layout", icon="GREASEPENCIL")
        box.operator("popup.draw_holes", icon="MOD_BOOLEAN")
        row = box.row(align=True)
        row.operator("popup.build", text="Cut", icon="FILE_REFRESH")
        row.operator("popup.keep_holes", text="Keep", icon="CHECKMARK").edit = False
        row.operator("popup.keep_holes", text="Edit", icon="GREASEPENCIL").edit = True


class POPUP_PT_checks(_Base, bpy.types.Panel):
    """Right under the card: what would tear, collide or stick out, in red
    when there's anything to fix"""
    bl_label = ""
    bl_order = 1

    @classmethod
    def poll(cls, context):
        return context.scene.popup.rig is not None

    def draw_header(self, context):
        n = len(context.scene.popup.warnings.splitlines())
        row = self.layout.row()
        row.alert = n > 0
        row.label(text=f"Checks: {n} to fix" if n else "Checks: all clear",
                  icon="ERROR" if n else "CHECKMARK")

    def draw(self, context):
        ws = context.scene.popup.warnings.splitlines()
        if not ws:
            self.layout.label(text="Folds flat, opens flat, no collisions found")
            return
        col = self.layout.column(align=True)
        col.alert = True
        for w in ws:
            col.label(text=w, icon="ERROR")


class POPUP_PT_art(_Base, bpy.types.Panel):
    bl_label = "Artwork"
    bl_order = 4

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
        col.prop(st, "true_colours")
        from . import images
        images.draw(lay, context)
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
    bl_order = 5
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        return context.scene.popup.rig is not None

    def draw(self, context):
        draw_export(self.layout, context.scene.popup)
        self.layout.operator("popup.export_svg", icon="EXPORT")


classes = (POPUP_UL_lines, POPUP_UL_mechs, POPUP_UL_openings, POPUP_MT_add, POPUP_PT_card,
           POPUP_PT_mechs,
           POPUP_PT_openings, POPUP_PT_checks,
           POPUP_PT_art, POPUP_PT_export)


def register():
    for c in classes:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
