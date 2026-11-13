import bpy

from . import live

KIND_ICON = {"VFOLD": "MOD_TRIANGULATE", "BOX": "MESH_CUBE", "BOXCUT": "SNAP_FACE",
             "MOUTH": "MOD_SIMPLEDEFORM", "CUBE": "CUBE", "FLAP": "MOD_CLOTH",
             "TUBE": "MESH_CYLINDER", "TETHER": "LINKED",
             "PYRAMID": "CONE", "FRAME": "IMAGE_PLANE", "FLOOR": "TRIA_DOWN_BAR",
             "CEILING": "TRIA_UP_BAR", "STAGE": "IMAGE_BACKGROUND",
             "STANDUP": "OUTLINER_OB_IMAGE", "ROOF": "HOME", "PLATFORM": "MOD_SOLIDIFY",
             "RISER": "OUTLINER_OB_FORCE_FIELD", "BOXEND": "MESH_CUBE", "DOUBLE45": "ORIENTATION_GIMBAL",
             "ZIGZAG": "MOD_SCREW", "QUADS": "MOD_LATTICE",
             "JACK": "OUTLINER_OB_ARMATURE", "PICTURE": "IMAGE_DATA"}


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
        row = layout.row(align=True)
        row.prop(item, "selected", text="")
        row.prop(item, "label", text="", emboss=False, icon=KIND_ICON[item.kind])
        icon = {"NORMAL": "HIDE_OFF", "WIRE": "SHADING_WIRE", "HIDDEN": "HIDE_ON"}[
            item.visibility]
        op = row.operator("popup.visibility", text="", icon=icon, emboss=False)
        op.action, op.uid = "CYCLE", item.uid


class POPUP_MT_visibility(bpy.types.Menu):
    bl_label = "Visibility"
    bl_idname = "POPUP_MT_visibility"

    def draw(self, context):
        lay = self.layout
        lay.operator("popup.visibility", text="Show All", icon="HIDE_OFF").action = "ALL"
        lay.operator("popup.visibility", text="Isolate Selected (others hidden)",
                     icon="HIDE_ON").action = "ISOLATE"
        lay.operator("popup.visibility", text="Others as Wire",
                     icon="SHADING_WIRE").action = "WIRE_OTHERS"
        lay.separator()
        lay.label(text="Click the eye in a row to cycle it")


class POPUP_MT_add(bpy.types.Menu):
    bl_label = "Add Mechanism"
    bl_idname = "POPUP_MT_add"

    def draw(self, context):
        """A column for each place things go: on the card's fold (two columns,
        by family), in a stage, and on the selected mechanism."""
        from .props import is_angled
        st = context.scene.popup
        row = self.layout.row()
        self.draw_on_fold(row.column(), row.column())
        self.draw_stage(row.column(), st)
        if not st.mechs or st.active >= len(st.mechs):
            return
        h = st.mechs[st.active]  # the selected mechanism: what can go on it
        takes = (h.kind in ("FLOOR", "CEILING", "ZIGZAG", "QUADS", "STAGE", "CUBE", "TUBE",
                            "PLATFORM")
                 or h.kind == "VFOLD" and h.shape != "FAN"
                 or h.kind in ("BOX", "BOXCUT", "STANDUP") and not is_angled(h, st.mechs))
        if not takes:
            return
        lay = row.column()
        lay.label(text="On What's Selected", icon=KIND_ICON.get(h.kind, "DOT"))
        if h.kind in ("FLOOR", "CEILING"):
            self.draw_in_corners(lay, h)
        elif h.kind in ("ZIGZAG", "QUADS") or h.kind == "VFOLD" and h.shape != "FAN":
            self.draw_on_vfold(lay, h)
        elif h.kind == "STAGE":
            self.draw_in_stage(lay, h)
        if h.kind in ("CUBE", "TUBE"):
            self.draw_outside_walls(lay, st, h)
        if h.kind in ("BOX", "BOXCUT", "STANDUP") and not is_angled(h, st.mechs):
            self.draw_on_box(lay, h)
        if h.kind == "PLATFORM":
            self.draw_on_platform(lay, h)

    @staticmethod
    def _adds(lay, heading, entries):
        """A heading and its Adds: (text, kind) or (text, kind, variant) each."""
        lay.label(text=heading)
        for text, kind, *variant in entries:
            op = lay.operator("popup.add", text=text, icon=KIND_ICON[kind])
            op.kind = kind
            if variant:
                op.variant = variant[0]

    def draw_on_fold(self, one, two):
        """Everything that goes on the card's fold, by family, in two columns."""
        one.label(text="On the Card's Fold", icon="MOD_TRIANGULATE")
        self._adds(one, "V-folds:", (
            ("V-fold", "VFOLD"), ("V-fold (asymmetric)", "VFOLD", "ASYM"),
            ("Mouth (cut in)", "MOUTH"), ("Jack in the Box (on a V-fold)", "JACK"),
            ("Multiple Quadrilaterals (angled strips)", "QUADS")))
        one.separator()
        self._adds(one, "Box folds:", (
            ("Box Fold / Strap (glued strip)", "BOX"),
            ("Box Fold (angled glue lines)", "BOX", "ANGLED"),
            ("Box Layer (cut in)", "BOXCUT"), ("Stand-up (parallelogram)", "STANDUP")))
        one.separator()
        self._adds(one, "45° folds:", (
            ("Platform (45° folds)", "PLATFORM"), ("Rising Sheet (45° folds)", "RISER"),
            ("Double 45° Fold (twisting top)", "DOUBLE45"),
            ("Box with Ends (on one page, 45° folds)", "BOXEND")))
        two.label(text="")
        self._adds(two, "Cubes and tubes:", (
            ("Cube (180°)", "CUBE"), ("Pop-up House (cube, gabled roof)", "CUBE", "HOUSE"),
            ("Tube (parallel strips)", "TUBE"),
            ("Castle (tube with corner towers)", "TUBE", "CASTLE"),
            ("Loop (ring on two tabs)", "TUBE", "LOOP"),
            ("Animal Face (loop with a muzzle)", "TUBE", "FACE"),
            ("Pyramid / Tent (parallel strips)", "PYRAMID"), ("Tether", "TETHER")))
        two.separator()
        self._adds(two, "Roofs:", (
            ("Roof (peaked, cuts a gable)", "ROOF"),
            ("Valley Floor (roof upside down)", "ROOF", "VALLEY")))
        two.separator()
        self._adds(two, "On a page or a face:", (
            ("Pull-tab Flap", "FLAP"), ("Picture (glued on a face)", "PICTURE")))

    def draw_stage(self, lay, st):
        """Stages: a stage set in a card, a frame across the fold; and, when
        the card is itself the stage (a carousel's, or one that Opens To
        under 180), its frames, floor and ceiling."""
        lay.label(text="Stage", icon=KIND_ICON["STAGE"])
        if not st.part_open:
            lay.operator("popup.add", text="Frame (across the fold, pulls flat)",
                         icon=KIND_ICON["FRAME"]).kind = "FRAME"
        if st.stage_master is None:
            lay.operator("popup.add", text="Stage Set (V-fold)",
                         icon=KIND_ICON["STAGE"]).kind = "STAGE"
        if st.part_open:
            lay.separator()
            lay.label(text="In this stage:" if st.stage_master is not None else
                      f"In the card (opens to {st.open_max:.0f}°):")
            for k, name in (("FRAME", "Frame"), ("FLOOR", "Floor"), ("CEILING", "Ceiling")):
                lay.operator("popup.add", text=name, icon=KIND_ICON[k]).kind = k

    def draw_in_corners(self, lay, h):
        """With a floor or ceiling selected: what stands where it meets a wall."""
        lay.separator()
        lay.label(text=f"In the corners of {h.label}:")
        for k, name in (("BOX", "Box Fold"), ("VFOLD", "V-fold"), ("CUBE", "Cube")):
            for side, wall in (("L", "left wall"), ("R", "right wall")):
                op = lay.operator("popup.add", text=f"{name}, {wall}",
                                          icon=KIND_ICON[k])
                op.kind, op.host, op.side = k, h.uid, side
        op = lay.operator("popup.add", text="V-fold on its crease",
                                  icon=KIND_ICON["VFOLD"])
        op.kind, op.host, op.fold = "VFOLD", h.uid, "V"

    def draw_on_vfold(self, lay, h):
        """With a V-fold, zig-zag or quadrilaterals selected: what stands on its
        crease and (a V-fold's) glue folds."""
        glued = h.kind == "VFOLD" and h.shape not in ("M", "ZIGZAG")
        lay.separator()
        lay.label(text=f"On {h.label}:")
        for kind, text in (("BOX", "Box Fold on the Crease"),
                           ("BOXCUT", "Box Layer cut in the Crease"),
                           ("VFOLD", "V-fold on the Crease"),
                           ("MOUTH", "Mouth cut in the Crease"),
                           ("STANDUP", "Stand-up on the Crease")):
            op = lay.operator("popup.add", text=text, icon=KIND_ICON[kind])
            op.kind, op.host, op.fold = kind, h.uid, "V"
            if kind == "VFOLD" and glued:
                op = lay.operator("popup.add", text="V-fold on Top (tabs A)",
                                          icon=KIND_ICON[kind])
                op.kind, op.host, op.fold, op.variant = kind, h.uid, "V", "TOP"
        for kind, text in (("CUBE", "Cube in the V (on the Crease)"),
                           ("TUBE", "Tube in the V (on the Crease)")):
            op = lay.operator("popup.add", text=text, icon=KIND_ICON[kind])
            op.kind, op.host, op.fold = kind, h.uid, "V"
        if glued:
            lay.label(text="On its glue folds (off-centre):")
        for fold, where in ((("FL", "in front, left"), ("FR", "in front, right"),
                            ("BL", "behind, left"), ("BR", "behind, right")) if glued else ()):
            for kind, name in (("STANDUP", "Stand-up"), ("CUBE", "Cube"),
                               ("TUBE", "Tube"), ("VFOLD", "V-fold"),
                               ("BOX", "Box Fold")):
                if fold[0] == "B" and kind != "STANDUP":
                    continue  # inside the V there's little room: stand-ups only
                op = lay.operator("popup.add", text=f"{name} {where}",
                                          icon=KIND_ICON[kind])
                op.kind, op.host, op.fold = kind, h.uid, fold

    def draw_in_stage(self, lay, h):
        """With a stage set selected: its frames and ceiling."""
        lay.separator()
        lay.label(text=f"In {h.label}:")
        for k, name in (("FRAME", "Frame"), ("CEILING", "Ceiling")):
            op = lay.operator("popup.add", text=name, icon=KIND_ICON[k])
            op.kind, op.host = k, h.uid

    def draw_outside_walls(self, lay, st, h):
        """With a cube or tube selected: what stands outside its walls, balconies,
        and a tube's towers."""
        lay.separator()
        lay.label(text=f"Outside the walls of {h.label}:")
        for wall, where in (("L", "left wall"), ("R", "right wall")):
            for kind, name in (("CUBE", "Cube"), ("TUBE", "Tube"), ("VFOLD", "V-fold"),
                               ("BOX", "Box Fold"), ("BALCONY", "Balcony"),
                               ("STANDUP", "Stand-up")):
                op = lay.operator("popup.add", text=f"{name}, {where}",
                                          icon=KIND_ICON["BOX" if kind == "BALCONY"
                                                         else kind])
                op.kind, op.host, op.fold = ("BOX" if kind == "BALCONY" else kind,
                                             h.uid, "W" + wall)
                if kind == "BALCONY":
                    op.variant = "BALCONY"
        op = lay.operator("popup.add", text="Balconies on Both Side Walls",
                                  icon=KIND_ICON["BOX"])
        op.kind, op.host, op.variant = "BOX", h.uid, "BALCONIES"
        if h.kind == "TUBE" and any(x.kind == "BOX" and x.host_uid == h.uid and
                                    x.wall.startswith("K") for x in st.mechs):
            op = lay.operator("popup.add", text="Balconies Outside the Towers",
                                      icon=KIND_ICON["BOX"])
            op.kind, op.host, op.variant = "BOX", h.uid, "TOWER_BALCONIES"
        from .ops import tube_corners
        corners = tube_corners(st, h.uid) if h.kind == "TUBE" else []
        if corners:  # (round ends have none)
            lay.label(text=f"Towers in the corners of {h.label}:")
            op = lay.operator("popup.add", text="Tower in Every Inside Corner",
                                      icon=KIND_ICON["BOX"])
            op.kind, op.host, op.variant = "BOX", h.uid, "TOWERS"
            names = {"KFL": "front left corner", "KFR": "front right corner",
                     "KBR": "back right corner", "KBL": "back left corner",
                     "KF": "front crease", "KB": "back crease"}
            for fold in corners:
                op = lay.operator("popup.add", text=f"Tower, {names[fold]}",
                                          icon=KIND_ICON["BOX"])
                op.kind, op.host, op.fold = "BOX", h.uid, fold

    def draw_on_box(self, lay, h):
        """With a box fold, box layer or stand-up selected: what stands on top of
        it, in front of it, and in a strap's valleys."""
        lay.separator()
        lay.label(text=f"On {h.label}:")
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
            if fold == "C" and h.kind == "BOX" and h.peaks > 1:
                continue  # several peaks: the top doesn't meet the front (use a valley)
            op = lay.operator("popup.add", text=text, icon=KIND_ICON[kind])
            op.kind, op.host, op.fold = kind, h.uid, fold
            if kind == "BOX" and fold == "B":
                op = lay.operator("popup.add", text="Balcony in Front",
                                          icon=KIND_ICON["BOX"])
                op.kind, op.host, op.fold, op.variant = "BOX", h.uid, "B", "BALCONY"
        if h.kind == "BOX" and h.peaks > 1:
            for kind, name in (("CUBE", "Cube"), ("TUBE", "Tube"), ("VFOLD", "V-fold"),
                               ("STANDUP", "Stand-up")):
                op = lay.operator("popup.add", text=f"{name} in a Valley",
                                          icon=KIND_ICON[kind])
                op.kind, op.host, op.fold = kind, h.uid, "VAL"

    def draw_on_platform(self, lay, h):
        """With a platform selected: what stands in the valley of its top."""
        lay.separator()
        lay.label(text=f"On top of {h.label}:")
        for kind, name in (("BOX", "Box Fold"), ("VFOLD", "V-fold"), ("CUBE", "Cube"),
                           ("TUBE", "Tube"), ("STANDUP", "Stand-up")):
            op = lay.operator("popup.add", text=name, icon=KIND_ICON[kind])
            op.kind, op.host, op.fold = kind, h.uid, "A"


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


def _tower_top(col, m, cube=False):
    """A tower's (or cube's) roof and collar settings."""
    col.prop(m, "roof", text="Tower Roof" if cube else "Roof")
    if m.roof == "POINTED":
        col.prop(m, "roof_height")
    elif m.roof == "GABLE":
        col.prop(m, "roof_height", text="Gable Height")
        col.prop(m, "eave")
        col.prop(m, "gable_turn")
    elif m.roof == "FLAT":
        col.prop(m, "roof_slope")
        if not cube:
            col.prop(m, "roof_below")
        if m.roof_below > 0 and not cube:
            col.prop(m, "battlements")
        else:
            col.prop(m, "eave")
    col.prop(m, "collar")
    if m.collar:
        col.prop(m, "collar_dir", text="Shape")
        if m.collar_dir == "OUT":
            col.prop(m, "collar_below")
        col.prop(m, "collar_width")
        col.prop(m, "collar_slope")
        col.prop(m, "collar_corner")
        if m.collar_corner == "SLIDE":
            col.prop(m, "collar_gap")
        col.prop(m, "collar_rail")
        if m.collar_rail > 0:
            col.prop(m, "collar_crenels")
            col.prop(m, "collar_tiers")
            if m.collar_tiers > 1:
                col.prop(m, "collar_alternate")


def _where(col, st, m):
    """Where a mechanism stands: the same few words for every kind."""
    from .props import crease_only
    col.prop(m, "host", text="Stands On")
    hm = next((h for h in st.mechs if h.uid == m.host_uid), None) if m.host_uid else None
    if hm is not None and hm.kind in ("BOX", "BOXCUT", "STANDUP"):
        col.prop(m, "fold", text="Fold")
        if hm.kind == "BOX" and m.fold == "V":
            col.prop(m, "gully")
    if hm is not None and (crease_only(hm) or m.kind == "JACK" and hm.kind == "VFOLD"):
        # only one place to stand: nothing to choose
        col.label(text="On its centre crease", icon="INFO")
    elif hm is not None and hm.kind == "VFOLD":
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
        col.prop(st, "opens_to")
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
            top = st.open_max  # (quarters of the way open)
            for a in (0, 45, 90, 135, 180) if top > 179.5 else [round(top * k / 4) for k in range(5)]:
                row.operator("popup.set_open", text=f"{a}°").angle = a
            draw_anim(box, context.scene, st, "anim_to")
            _paper(box, st, rig)
        if st.rig is None:
            self.layout.separator()
            self.layout.operator("popup.make_carousel", icon="MESH_CIRCLE")
        row = self.layout.row(align=True)
        row.operator("popup.setup_scene", icon="SHADING_RENDERED")
        row.prop(st, "render_look", text="", icon="LIGHT_SUN")
        row.prop(st, "layout_in_render", text="", icon="UV")

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
        row.prop(st, "layout_in_render", text="", icon="UV")
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


def _align(lay, st):
    """Align: shown once more than one mechanism is picked (or to put one
    against its fold's ends or the card's edges)."""
    n = sum(1 for i, m in enumerate(st.mechs) if m.selected or i == st.active)
    head, box = lay.panel("popup_align", default_closed=True)
    head.label(text=f"Align ({n})" if n > 1 else "Align", icon="ALIGN_CENTER")
    if box is None:
        return
    row = box.row(align=True)
    row.label(text="Pick:")
    for a, txt in (("FOLD", "Same Fold"), ("ALL", "All"), ("NONE", "None")):
        row.operator("popup.select_mechs", text=txt).action = a
    box = box.column()
    box.active = n > 1 or st.align_to == "HOST"
    row = box.row(align=True)
    row.prop(st, "align_scope", expand=True)
    box.prop(st, "align_to", text="To")
    row = box.row(align=True)
    if st.align_scope == "FOLD":
        for h, ic in (("START", "ALIGN_LEFT"), ("CENTRE", "ALIGN_CENTER"),
                      ("END", "ALIGN_RIGHT")):
            op = row.operator("popup.align", text="", icon=ic)
            op.how = h
        row.separator()
        row.operator("popup.align", text="Distribute", icon="ALIGN_JUSTIFY").how = "DISTRIBUTE"
    else:
        for h, ic in (("BOTTOM", "ANCHOR_BOTTOM"), ("VCENTRE", "ALIGN_MIDDLE"),
                      ("TOP", "ANCHOR_TOP")):
            row.operator("popup.align", text="", icon=ic).how = h
        row.operator("popup.align", text="Up", icon="ALIGN_JUSTIFY").how = "DIST_V"
        row = box.row(align=True)
        row.label(text="Flaps (from spine):")
        for h, ic in (("INNER", "ANCHOR_LEFT"), ("HCENTRE", "ANCHOR_CENTER"),
                      ("OUTER", "ANCHOR_RIGHT")):
            row.operator("popup.align", text="", icon=ic).how = h
        row.operator("popup.align", text="Across", icon="ALIGN_JUSTIFY").how = "DIST_H"


# the Mechanisms panel: kinds with a layout all their own (methods of the panel)
_OWN_PANELS = {"TUBE": "draw_tube", "PICTURE": "draw_picture", "STAGE": "draw_stage",
               "FRAME": "draw_frame", "FLOOR": "draw_floor", "CEILING": "draw_floor",
               "PYRAMID": "draw_pyramid", "ROOF": "draw_roof", "TETHER": "draw_tether"}
# kinds placed on a fold (Stands On and Position first), then their own settings;
# anything else is a box fold
_PLACED_PANELS = {"CUBE": "draw_cube", "MOUTH": "draw_mouth", "PLATFORM": "draw_platform",
                  "RISER": "draw_riser", "BOXEND": "draw_boxend", "JACK": "draw_jack", "ZIGZAG": "draw_linkage",
                  "QUADS": "draw_linkage", "DOUBLE45": "draw_double45", "STANDUP": "draw_standup"}


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
        col.menu("POPUP_MT_visibility", text="", icon="HIDE_OFF")
        if not st.mechs or st.active >= len(st.mechs):
            return
        _align(lay, st)
        m = st.mechs[st.active]
        col = lay.column()
        col.use_property_split = True
        col.use_property_decorate = False
        col.prop(m, "kind", text="Type")
        if m.kind == "FLAP":
            self.draw_flap(context, col, m)
            return
        own = _OWN_PANELS.get(m.kind)
        if own:
            getattr(self, own)(context, st, col, m)
            return
        hm = _where(col, st, m)
        joint = hm is not None and hm.kind in ("FLOOR", "CEILING")
        if joint and m.kind == "VFOLD":
            col.prop(m, "on_crease")
        if joint and not (m.kind == "VFOLD" and m.on_crease):
            col.prop(m, "side", text="Wall")
        if m.kind == "VFOLD" and m.on_top and m.host_uid and (m.vside == "V" or m.on_crease):
            col.label(text="At the top of the lifting piece's crease", icon="INFO")
        else:
            col.prop(m, "y", text="Position")
        if m.kind == "VFOLD":
            self.draw_vfold(context, col, m)
            return
        getattr(self, _PLACED_PANELS.get(m.kind, "draw_box"))(col, m, hm, joint)
        if m.kind in ("CUBE", "STANDUP", "BOX", "PLATFORM", "RISER", "DOUBLE45", "ZIGZAG",
                      "QUADS", "BOXEND"):
            _tabs(self.layout, m, side=m.kind == "CUBE")
        if m.kind in ("BOX", "BOXCUT"):
            _draw_lines(self.layout, context, m)
        self.draw_warnings(context, m)

    def draw_tube(self, context, st, col, m):
        """Tubes, cylinders, loops and cones."""
        _where(col, st, m)
        col.prop(m, "y", text="Position")
        col.prop(m, "x", text="Strip Distance")
        col.prop(m, "depth", text="Length Along Fold")
        col.prop(m, "height")
        col.prop(m, "front")
        col.prop(m, "front_style")
        col.prop(m, "back")
        col.prop(m, "back_style")
        if "ROUND" in (m.front_style, m.back_style):
            import math as _m
            col.label(text=f"Round: {0.5 * _m.pi * m.x:.1f} mm makes a half circle",
                      icon="INFO")
        if m.kind == "TUBE" and m.front_style == "ROUND" and m.back_style == "ROUND":
            col.prop(m, "cone_top")
            col.prop(m, "cone_lean")  # (the same thing, as an angle)
        if m.kind == "TUBE":
            col.prop(m, "muzzle")
            if m.muzzle:
                col.prop(m, "face_width")
                col.prop(m, "face_len")
                col.prop(m, "face_dart")
        col.prop(m, "strips")
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

    def draw_picture(self, context, st, col, m):
        """A picture glued on a face."""
        col.prop(m, "pic_on")
        col.prop(m, "pic_face")
        col.prop(m, "pic_side")
        col.prop(m, "pic_x", text="X (corner, across)")
        col.prop(m, "pic_y", text="Y (corner, up)")
        col.prop(m, "img_w", text="Width")
        col.prop(m, "img_h", text="Height")
        col.prop(m, "pic_turn")
        col.label(text="Draw on it, or erase its art to shape it", icon="INFO")
        self.draw_warnings(context, m)

    def draw_stage(self, context, st, col, m):
        """A stage set standing in a card."""
        col.prop(m, "y", text="Position")
        col.prop(m, "phi_l", text="Glue Angle")
        col.label(text=f"Opens to {2 * m.phi_l:.0f}° when the card is flat", icon="INFO")
        col.prop(m, "glue", text="Glue Length (half width)")
        col.prop(m, "height")
        _tabs(self.layout, m)
        self.draw_warnings(context, m)

    def draw_frame(self, context, st, col, m):
        """A stage's frame, or one across the card's fold."""
        import math as _m
        tmax = st.open_max
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

    def draw_floor(self, context, st, col, m):
        """A stage's floor or ceiling."""
        if st.stage_master is None:
            col.prop(m, "host", text="Stage" if not st.part_open else "In")
        col.prop(m, "depth")
        col.prop(m, "lead")
        _tabs(self.layout, m, side=False)
        self.draw_warnings(context, m)

    def draw_pyramid(self, context, st, col, m):
        """Pyramids and tents."""
        _where(col, st, m)
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

    def draw_roof(self, context, st, col, m):
        """A peaked roof, or a valley floor."""
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

    def draw_tether(self, context, st, col, m):
        """A tether."""
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

    def draw_cube(self, col, m, hm, joint):
        """A cube's own settings."""
        col.prop(m, "size", text="Width" if m.size_r <= 0 else "Width Left")
        col.prop(m, "size_r", text="Width Right (0 = square)" if m.size_r <= 0
                 else "Width Right")
        col.prop(m, "height")
        row = col.row()
        row.active = (m.size_r <= 0 or abs(m.size_r - m.size) < 1e-6) and m.roof in \
            ("NONE", "GABLE")
        row.prop(m, "lid")
        _tower_top(col, m, cube=True)

    def draw_mouth(self, col, m, hm, joint):
        """A mouth's own settings."""
        col.prop(m, "jaw")
        col.prop(m, "upper")
        col.prop(m, "lower")

    def draw_platform(self, col, m, hm, joint):
        """A platform's own settings."""
        col.prop(m, "width", text="Length Along Fold")
        col.prop(m, "height", text="Leg Height")
        col.prop(m, "depth", text="Out Left" if m.depth_r > 0 else "Out Each Side")
        col.prop(m, "depth_r", text="Out Right (0 = same)")
        col.prop(m, "brace")
        if m.brace != "NONE":
            col.prop(m, "brace_size")

    def draw_boxend(self, col, m, hm, joint):
        """A box with ends' own settings."""
        col.prop(m, "box_side")
        col.prop(m, "width", text="Length Along Fold")
        col.prop(m, "depth", text="Width (out from the fold)")
        col.prop(m, "height", text="Wall Height")
        col.prop(m, "box_ends")
        col.prop(m, "brace_size", text="Pulling 45° Fold Size")

    def draw_riser(self, col, m, hm, joint):
        """A rising sheet's own settings."""
        col.prop(m, "width", text="Width Along Fold")
        col.prop(m, "height", text="Sheet Height")
        col.prop(m, "brace_size")
        col.prop(m, "slotted")
        if m.slotted:
            col.prop(m, "cross_height", text="Cross Piece Height (0 = auto)")
            col.prop(m, "cross_width", text="Cross Piece Width (0 = the folds)")
        col.label(text="Shape the sheet by erasing its art (Paint, Erase)", icon="INFO")

    def draw_jack(self, col, m, hm, joint):
        """A jack in the box's own settings."""
        col.prop(m, "height", text="Fold Spacing (G)")
        col.prop(m, "depth", text="Arm Reach")
        col.label(text="Draw the figure; erase its art to shape it", icon="INFO")

    def draw_linkage(self, col, m, hm, joint):
        """A zig-zag's or multiple quadrilaterals' own settings."""
        col.label(text="Glue lines meet the spine at Position")
        col.prop(m, "phi_l", text="Glue Angle")
        col.prop(m, "x", text="Glued From")
        col.prop(m, "width", text="Glue Length (end walls)")
        if m.kind == "ZIGZAG":
            col.prop(m, "faces", text="Faces (end in, mm)")
            col.prop(m, "jut")
            col.prop(m, "height")
        else:
            col.prop(m, "q_back1")
            col.prop(m, "q_back2")
            col.prop(m, "q_side", text="Side (back crease to front)")
            col.prop(m, "q_front", text="Front (to centre)")
            col.prop(m, "height", text="Back Height")
            col.prop(m, "q_side_h")
            col.prop(m, "q_front_h")
            col.label(text="Side's face to the strip: worked out so it folds flat",
                      icon="INFO")
        col.prop(m, "cut_bottoms")

    def draw_double45(self, col, m, hm, joint):
        """A double 45's own settings."""
        col.prop(m, "width", text="Arm Width")
        col.prop(m, "height", text="Arm Length")
        col.prop(m, "depth", text="Top Piece Length")
        col.label(text="Top piece longer than both arms together", icon="INFO")

    def draw_standup(self, col, m, hm, joint):
        """A stand-up's own settings."""
        flat = m.stand == "FLAT"
        col.prop(m, "stand")
        col.prop(m, "width", text="Leg Width" if flat else (
            "Tail Width" if m.stand == "TAIL" else "Bridge Width"))
        col.prop(m, "height", text="Height Above Floor" if flat else "Bridge Height")
        col.prop(m, "depth", text="Leg Out From Back" if flat else "Out From Back")
        col.prop(m, "img_w")
        col.prop(m, "img_h", text="Picture Depth" if flat else "Picture Height")
        col.label(text="Shape the picture by erasing its art (Paint, Erase)",
                  icon="INFO")

    def draw_vfold(self, context, col, m):
        """A V-fold's own settings (every shape), to the end of the panel."""
        col.prop(m, "shape")
        if m.shape == "ZIGZAG":
            col.prop(m, "height", text="Wall Height")
            col.prop(m, "phi_l", text="Glue Angle")
            col.prop(m, "glue_from", text="Glued From")
            col.prop(m, "glue", text="Glue Length (end walls)")
            col.prop(m, "faces_n")
            col.prop(m, "faces_uneven")
            if m.faces_uneven:
                col.prop(m, "faces", text="Widths (mm, from the glued wall in)")
            else:
                col.prop(m, "face_w")
            col.prop(m, "jut")
            col.prop(m, "cut_bottoms")
            _tabs(self.layout, m, side=False)
            self.draw_warnings(context, m)
            return
        if m.shape == "M":
            col.prop(m, "height", text="Fold Length")
            col.prop(m, "phi_l", text="Glue Angle (B)")
            col.prop(m, "alpha_l", text="Piece Angle (A)")
            col.prop(m, "glue", text="Glue Length to the Bend")
            col.prop(m, "m_d", text="Angle D (= C on the page)" if not m.m_free else
                     "Angle D")
            col.prop(m, "m_e", text="Angle E (= F)" if not m.m_free else "Angle E")
            col.prop(m, "m_free")
            if m.m_free:
                col.prop(m, "m_c")
                col.prop(m, "m_f")
            col.prop(m, "m_outer_h", text="Crease Length (D and H)")
            col.prop(m, "m_outer_len", text="Outer Glue Length")
            col.prop(m, "glue_from")
            _tabs(self.layout, m)
            self.draw_warnings(context, m)
            return
        fan = m.shape == "FAN"
        col.prop(m, "height", text="Radius" if fan else "Fold Length")
        if fan:
            col.prop(m, "fan_pleats")
            col.prop(m, "fan_spread")
            col.prop(m, "fan_stand")
            col.prop(m, "phi_l", text="Glue Angle")
            col.prop(m, "glue_from", text="Glued From (hub cut away)")
            if not m.host_uid:
                col.prop(m, "cut_above")
            _tabs(self.layout, m)
            self.draw_warnings(context, m)
            return
        else:
            col.prop(m, "glue", text="Glue Length" if m.symmetric else "Glue Length L")
            if not m.symmetric:
                col.prop(m, "glue_r")
        col.prop(m, "symmetric")
        top = m.on_top and m.host_uid and (m.vside == "V" or m.on_crease)
        if top:
            col.prop(m, "top_angle", text="Point Angle" if m.symmetric else "Point Angle L")
            if not m.symmetric:
                col.prop(m, "top_angle_r")
            col.prop(m, "top_piece",
                     text="Top Piece Angle" if m.symmetric else "Top Piece Angle L")
            if not m.symmetric:
                col.prop(m, "top_piece_r")
            col.prop(m, "top_below")
            col.label(text="Point Angle over 90 makes a V-shaped top", icon="INFO")
        else:
            col.prop(m, "phi_l", text="Glue Angle" if m.symmetric else "Glue Angle L")
        if not m.symmetric and not top:
            col.prop(m, "phi_r")
            col.prop(m, "fold_flat")
        if top:
            pass
        elif not m.symmetric and m.fold_flat:
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
        if m.host_uid and (m.vside == "V" or m.on_crease):
            col.prop(m, "on_top")
        each = not m.symmetric or m.arch_uneven
        col.prop(m, "glue_from", text="Glued From L" if each else "Glued From")
        if each:
            col.prop(m, "glue_from_r")
        if m.glue_from > 0 or (each and m.glue_from_r > 0):
            if m.symmetric:
                col.prop(m, "arch_uneven")
                if m.arch_uneven:
                    col.prop(m, "glue_r")
            col.prop(m, "arch")
            col.prop(m, "arch_shape")
        _tabs(self.layout, m)
        _draw_lines(self.layout, context, m)
        self.draw_warnings(context, m)

    def draw_box(self, col, m, hm, joint):
        """A box fold's, strap's, box layer's or tower's own settings."""
        tower = m.kind == "BOX" and hm is not None and hm.kind == "TUBE" and \
            m.wall.startswith("K")
        col.prop(m, "width", text="Tower Height" if tower else "Length Along Fold")
        if joint:
            # which side of the joint each width lies on
            flat = "Along Floor" if hm.kind == "FLOOR" else "Along Ceiling"
            wall_first = (hm.kind == "FLOOR") == (m.side == "R")
            left, right = ("Up Wall", flat) if wall_first else (flat, "Up Wall")
            if hm.kind == "CEILING":
                left = left.replace("Up Wall", "Down Wall")
                right = right.replace("Up Wall", "Down Wall")
        elif tower:  # along each wall from the corner
            left, right = "Along Wall (left)", "Along Wall (right)"
        else:
            left, right = "Width Left", "Width Right"
        if m.kind == "BOX" and not joint and not tower:
            col.prop(m, "strap")
        if m.kind == "BOX" and not joint and not tower and abs(m.fan_angle) > 0.05:
            col.prop(m, "height", text="Out From Fold (bottom)" if m.fan_angle > 0
                     else "Out From Fold (bottom, narrowing up)")
        elif m.kind == "BOX" and m.strap and not joint:
            col.prop(m, "height", text="Width Each Side")
        else:
            col.prop(m, "height", text=left)
            col.prop(m, "depth", text=right)
        if tower:  # up a tube's inside corner
            _tower_top(col, m)
        angled = m.kind == "BOX" and not tower and not joint and abs(m.fan_angle) > 0.05
        if m.kind == "BOX" and not tower and not joint:
            col.prop(m, "fan_angle")
            if angled:
                col.prop(m, "fan_creases")
                col.prop(m, "fan_crease")
        if m.kind in ("BOX", "BOXCUT") and not tower and not angled:
            col.prop(m, "slant")
        if m.kind == "BOX" and not tower and not angled:
            col.prop(m, "peaks")
            if m.peaks <= 1:
                col.prop(m, "support")
                if m.support == "ARCHES":
                    col.prop(m, "bays")
                col.prop(m, "rail")
                if m.rail > 0:
                    col.prop(m, "rail_open")
        if m.kind in ("BOX", "BOXCUT") and not tower and not joint and not angled:
            col.prop(m, "tri45")
            if m.tri45 != "NONE":
                col.prop(m, "tri_size")
                col.prop(m, "tri_pic_layout")
                row = col.row(align=True)
                row.label(text="Pictures on them")
                for w_, t_ in (("LEFT", "Left"), ("RIGHT", "Right"), ("BOTH", "Both")):
                    op = row.operator("popup.tri_pictures", text=t_)
                    op.uid, op.which = m.uid, w_


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
    """In the mechanism's own settings: just how many creases and cuts it
    has; they are edited in Creases, Cuts and Holes."""
    row = lay.row()
    n = len(m.lines)
    txt = f"Creases and cuts: {n}" if n else "Creases and cuts: none"
    if n and m.pleat:
        txt += f", concertina {m.pleat:.0f}°"
    row.label(text=txt + "  (Creases, Cuts and Holes)", icon="MOD_LINEART")


def _mech_lines(lay, context, m):
    """The selected mechanism's extra creases and cuts."""
    if m.kind in ("BOX", "BOXCUT"):
        c = lay.column(align=True)
        c.scale_y = 0.7
        c.label(text="X: from the front's top fold (- over the top, + down the front)")
        c.label(text="Y: along from the box's end; Mirror flips end to end")
    else:
        c = lay.column(align=True)
        c.scale_y = 0.7
        c.label(text="X: across from the centre fold (left half -); Y: up it from the V")
    row = lay.row()
    row.template_list("POPUP_UL_lines", "", m, "lines", m, "active_line", rows=3)
    col = row.column(align=True)
    col.operator_menu_enum("popup.add_line", "preset", text="", icon="ADD")
    col.operator("popup.remove_line", text="", icon="REMOVE")
    r = lay.row()
    r.use_property_split = True
    r.use_property_decorate = False
    r.prop(m, "pleat", text="Concertina")
    if 0 <= m.active_line < len(m.lines):
        ln = m.lines[m.active_line]
        c = lay.column(align=True)
        c.use_property_split = True
        c.use_property_decorate = False
        _line_fields(c, ln)


def _card_lines(lay, context, st):
    """The card's own creases and cuts: the background folding in, and lines."""
    c = lay.column()
    c.use_property_split = True
    c.use_property_decorate = False
    c.prop(st, "ceiling", text="Top Folds In")
    if st.ceiling != "NONE":
        c.prop(st, "ceiling_drop")
        c.prop(st, "ceiling_slope")
        if st.ceiling == "PEAK":
            c.prop(st, "ceiling_lift")
    c.prop(st, "floor", text="Bottom Folds In")
    if st.floor != "NONE":
        c.prop(st, "floor_rise")
        c.prop(st, "floor_slope")
        if st.floor == "PEAK":
            c.prop(st, "floor_dip")
    lay.label(text="X: across from the spine (left page -); Y: up from the bottom")
    row = lay.row()
    row.template_list("POPUP_UL_lines", "card", st, "card_lines", st, "active_card_line",
                      rows=3)
    col = row.column(align=True)
    col.operator_menu_enum("popup.add_card_line", "preset", text="", icon="ADD")
    col.operator("popup.remove_card_line", text="", icon="REMOVE")
    if 0 <= st.active_card_line < len(st.card_lines):
        ln = st.card_lines[st.active_card_line]
        c = lay.column(align=True)
        c.use_property_split = True
        c.use_property_decorate = False
        _line_fields(c, ln)


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
    """Everything that cuts or creases the paper, in one place: openings
    (windows, doorways, door flaps), extra creases and cuts on the selected
    mechanism or the card, and lines and holes drawn by hand"""
    bl_label = "Creases, Cuts and Holes"
    bl_order = 3

    @classmethod
    def poll(cls, context):
        return context.scene.popup.rig is not None

    def draw(self, context):
        st = context.scene.popup
        lay = self.layout
        from .ops import drawing_anywhere
        if _drawing(context) and not drawing_anywhere(context):
            # (drawing art anywhere has its Done Drawing in Artwork)
            r = lay.row()
            r.alert = True
            r.scale_y = 1.4
            r.operator("popup.done_drawing", icon="CHECKMARK")
        # ---- openings
        head, body = lay.panel("popup_openings", default_closed=False)
        head.label(text=f"Openings: windows, doorways, door flaps ({len(st.openings)})",
                   icon="MOD_BOOLEAN")
        if body is not None:
            _draw_openings(body, context, st)
        # ---- creases and cuts, on the selected mechanism or the card
        from .ops import _lined_active
        m = _lined_active(context)
        n = len(m.lines) if (m is not None and st.lines_on == "MECH") else len(st.card_lines)
        head, body = lay.panel("popup_lines", default_closed=False)
        head.label(text=f"Creases and cuts ({n})", icon="MOD_LINEART")
        if body is not None:
            row = body.row(align=True)
            row.prop_enum(st, "lines_on", "MECH", text=m.label if m is not None else
                          "Select a V-fold or box", icon="MOD_SIMPLEDEFORM")
            row.prop_enum(st, "lines_on", "CARD", text="Card", icon="FILE_BLANK")
            if st.lines_on == "CARD":
                _card_lines(body, context, st)
            elif m is not None:
                _mech_lines(body, context, m)
            else:
                body.label(text="Creases and cuts go on V-folds, box folds, box layers and "
                           "roofs", icon="INFO")
        # ---- by hand on the flat layout
        head, body = lay.panel("popup_drawn", default_closed=True)
        head.label(text="Draw by hand (on the flat layout)", icon="GREASEPENCIL")
        if body is not None:
            row = body.row(align=True)
            row.operator("popup.draw_lines", text="Creases", icon="GREASEPENCIL").kind = "CREASE"
            row.operator("popup.draw_lines", text="Cuts", icon="GREASEPENCIL").kind = "CUT"
            row.operator("popup.draw_holes", text="Holes", icon="MOD_BOOLEAN")
            c = body.column(align=True)
            c.operator("popup.take_lines", text="Add Drawn Creases and Cuts", icon="CHECKMARK")
            row = c.row(align=True)
            row.operator("popup.build", text="Cut Drawn Holes", icon="MOD_BOOLEAN")
            row.operator("popup.keep_holes", text="Keep", icon="PINNED").edit = False
            row.operator("popup.keep_holes", text="Edit", icon="GREASEPENCIL").edit = True
            c = body.column(align=True)
            c.scale_y = 0.8
            c.label(text="Creases and cuts go onto the piece they're drawn on;")
            c.label(text="closed outlines drawn as holes are cut out")



def _draw_openings(lay, context, st):
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
        st = context.scene.popup
        ws = st.warnings.splitlines()
        if not ws:
            self.layout.label(text="Folds flat, opens flat, no collisions found")
        else:
            from .ops import warned_mech
            col = self.layout.column(align=True)
            col.alert = True
            for w in ws:
                m = warned_mech(st, w)
                if m is None:
                    col.label(text=w, icon="ERROR")
                else:  # click it to select the mechanism it's about
                    row = col.row()
                    row.alignment = "LEFT"
                    row.operator("popup.select_warned", text=w, icon="ERROR",
                                 emboss=False).uid = m.uid
        _plan_view(self.layout, st)


def _plan_view(lay, st):
    """Plan view: the card squashed flat along the view, see-through."""
    box = lay.box()
    row = box.row(align=True)
    if st.plan_view:  # on: hard to miss, and plainly how to get back
        row.alert = True
        row.scale_y = 1.4
        row.prop(st, "plan_view", text="Turn Off Plan View", icon="CANCEL", toggle=True)
    else:
        row.prop(st, "plan_view", text="Plan View (see overlaps)", icon="XRAY", toggle=True)
    if not st.plan_view:
        return
    col = box.column()
    col.use_property_split = True
    col.use_property_decorate = False
    row = col.row(align=True)
    sub = row.row(align=True)
    sub.active = not st.plan_use_open
    sub.prop(st, "plan_angle", slider=True)
    row.prop(st, "plan_use_open", text="", icon="LINKED")
    col.prop(st, "plan_colour", expand=True)
    col.prop(st, "plan_depth", slider=True)
    col.prop(st, "plan_alpha", slider=True)
    col.prop(st, "plan_clashes")
    if st.plan_clashes:
        found = list(st.id_data.get("pop_clashes", []))
        if not found:
            col.label(text="No clashes at this opening", icon="CHECKMARK")
        for txt in found[:6]:
            col.label(text=txt, icon="ERROR")
        if len(found) > 6:
            col.label(text=f"and {len(found) - 6} more")


def _ink_layers(lay, context):
    """The ink layers, top one first: which one new strokes go on, show or
    hide, opacity, order; Edit Ink and Update Paper."""
    from . import ink
    sc = context.scene
    layers = ink.layers(sc)
    obj = ink.ink_object(sc, create=False)
    active = obj.data.layers.active if obj is not None else None
    box = lay.box()
    row = box.row(align=True)
    row.label(text=f"Ink Layers ({len(layers)})", icon="RENDERLAYERS")
    row.operator("popup.ink_layer", text="", icon="ADD").action = "ADD"
    if not layers:
        c = box.column(align=True)
        c.scale_y = 0.8
        c.label(text="What you draw is kept as strokes here,")
        c.label(text="to hide, reorder or edit later")
        return
    col = box.column(align=True)
    for i in range(len(layers) - 1, -1, -1):
        la = layers[i]
        row = col.row(align=True)
        op = row.operator("popup.ink_layer", text="", emboss=False,
                          icon="RADIOBUT_ON" if la == active else "RADIOBUT_OFF")
        op.action, op.index = "PICK", i
        row.prop(la, "name", text="")
        sub = row.row(align=True)
        sub.scale_x = 0.55
        sub.prop(la, "opacity", text="", slider=True)
        op = row.operator("popup.ink_layer", text="",
                          icon="HIDE_ON" if la.hide else "HIDE_OFF")
        op.action, op.index = "SHOW", i
        op = row.operator("popup.ink_layer", text="", icon="TRIA_UP")
        op.action, op.index = "UP", i
        op = row.operator("popup.ink_layer", text="", icon="TRIA_DOWN")
        op.action, op.index = "DOWN", i
        op = row.operator("popup.ink_layer", text="", icon="X")
        op.action, op.index = "REMOVE", i
    if not ink.editing(sc):
        row = box.row(align=True)
        row.operator("popup.ink_edit", icon="GREASEPENCIL")
        row.operator("popup.ink_update", icon="FILE_REFRESH")


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
        col.label(text="Draw (Grease Pencil)")
        from .ops import drawing_anywhere, sketching
        from . import ink
        on = sketching(context)
        if ink.editing(context.scene):
            c = col.column(align=True)
            c.scale_y = 0.8
            c.label(text="Editing the ink on the flat layout", icon="CHECKMARK")
            c.label(text="Any Grease Pencil mode and tool: move, erase, draw")
            _ink_layers(lay, context)
            if context.mode == "PAINT_GREASE_PENCIL":
                _ink_colour(lay, context)
            r = lay.row()
            r.alert = True
            r.scale_y = 1.3
            r.operator("popup.ink_done", icon="CHECKMARK")
        elif drawing_anywhere(context):
            c = col.column(align=True)
            c.scale_y = 0.8
            c.label(text="Drawing on the card, folded or flat", icon="CHECKMARK")
            c.label(text="Strokes go onto the paper when you're done")
            row = lay.row(align=True)
            row.scale_y = 1.3
            row.operator("popup.ink_paper", icon="TEXTURE")
            r = row.row(align=True)
            r.alert = True
            r.operator("popup.done_drawing", icon="CHECKMARK")
            lay.prop(st, "ink_in_front")
            _ink_colour(lay, context)
            _ink_layers(lay, context)
        elif on:
            meta = live.meta(st.rig)
            lab = next((p["label"] for p in meta["panels"] if p["name"] == on), on) \
                if meta else on
            col.prop(st, "sketch_panel", text="")
            col.operator("popup.sketch", text="Sketch on This Panel Instead",
                         icon="GREASEPENCIL").panel = ""
            c = col.column(align=True)
            c.scale_y = 0.8
            c.label(text=f"Sketching lines on {lab}", icon="CHECKMARK")
            _ink_colour(lay, context)
            r = lay.row()
            r.alert = True
            r.scale_y = 1.3
            r.operator("popup.done_drawing", icon="CHECKMARK")
        else:
            r = col.row()
            r.scale_y = 1.4
            r.operator("popup.draw_anywhere", icon="OUTLINER_OB_GREASEPENCIL")
            _ink_layers(lay, context)
            head, body = lay.panel("popup_sketch_lines", default_closed=True)
            head.label(text="Lines on One Panel (vector)")
            if body is not None:
                body.prop(st, "sketch_panel", text="")
                body.operator("popup.sketch", text="Sketch on Panel",
                              icon="GREASEPENCIL").panel = ""
        _erase_section(lay, context)
        from . import images
        images.draw(lay, context)
        from . import materials
        materials.draw(lay, context)
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


classes = (POPUP_UL_lines, POPUP_UL_mechs, POPUP_UL_openings, POPUP_MT_add,
           POPUP_MT_visibility, POPUP_PT_card,
           POPUP_PT_mechs,
           POPUP_PT_openings, POPUP_PT_checks,
           POPUP_PT_art, POPUP_PT_export)


def _drawing(context):
    from .ops import drawing
    try:
        return drawing(context)
    except (AttributeError, ReferenceError):
        return False


def _painting(context):
    from .ops import painting
    try:
        return painting(context)
    except (AttributeError, ReferenceError):
        return False


def _paint_controls(lay, context, big=False):
    """Paint on/off, and (with a paint layer on the paper, like Paint
    System's) what the brush paints into."""
    from .ops import paint_images, painting_into
    sc = context.scene
    on = _painting(context)
    row = lay.row(align=True)
    if big:
        row.scale_y = 1.4
    row.operator("popup.paint", text="Painting" if on else "Paint", icon="BRUSH_DATA",
                 depress=on).target = "TOGGLE"
    if not on:
        if big:
            box = lay.box()
            row = box.row(align=True)
            row.operator("popup.trace_holes", text="Cut Painted Holes", icon="MOD_BOOLEAN")
            row.operator("popup.trace_holes", text="", icon="X").clear = True
            box.prop(sc.popup, "auto_holes")
            from .ops import flat_layers
            mat = sc.popup.card.data.materials[0] if sc.popup.card.data.materials else None
            if flat_layers(mat) is not None:  # layers painting flat over the paper
                r = lay.row()
                r.alert = True
                r.operator("popup.light_layers", icon="LIGHT")
        return
    from .ops import erasing
    art_img, others = paint_images(sc)
    now = painting_into(sc)
    is_art = now is not None and now == art_img
    row.operator("popup.paint_erase", text="Erase" if big else "", icon="SELECT_SUBTRACT",
                 depress=erasing(sc))
    if others:
        row = lay.row(align=True)
        row.operator("popup.paint_into", text="Paper" if not big else "Paper (holes)",
                     icon="FILE_BLANK", depress=is_art).into = "ART"
        row.operator("popup.paint_into", text=(now.name if (now and not is_art) else "Layer"),
                     icon="RENDERLAYERS", depress=not is_art).into = (
            now.name if (now is not None and not is_art) else "OTHER")
    elif not is_art:
        row = lay.row(align=True)
        row.label(text=f"Painting into {now.name}" if now else "Painting into nothing",
                  icon="ERROR")
        row.operator("popup.paint_into", text="Paper", icon="FILE_BLANK").into = "ART"
    if big:
        c = lay.column(align=True)
        c.scale_y = 0.8
        c.label(text="Paint the folded card or the flat layout:", icon="INFO")
        c.label(text="they're the same paper")
        _brush_sections(lay, context)


def _erase_section(lay, context):
    """Erase the paper see-through (Texture Paint with an erasing brush) and
    cut what's erased out of it. Grease Pencil stays the way to draw."""
    from .ops import erasing
    sc = context.scene
    st = sc.popup
    on = _painting(context)
    head, body = lay.panel("popup_erase_paper", default_closed=not on)
    head.label(text="Erase the Paper (see-through)", icon="SELECT_SUBTRACT")
    if body is None:
        return
    if not on:
        r = body.row()
        r.scale_y = 1.3
        r.operator("popup.erase_paper", icon="SELECT_SUBTRACT")
    else:
        r = body.row(align=True)
        r.operator("popup.paint_erase", text="Erasing" if erasing(sc) else "Erase",
                   icon="SELECT_SUBTRACT", depress=erasing(sc))
        c = body.column(align=True)
        c.scale_y = 0.8
        c.label(text="Rub away the paper, folded or flat:", icon="INFO")
        c.label(text="they're the same paper")
        ip = sc.tool_settings.image_paint
        brush = getattr(ip, "brush", None)
        ups = getattr(sc.tool_settings, "unified_paint_settings", None)
        if brush is not None:
            src = ups if ups is not None and getattr(ups, "use_unified_size", False) \
                else brush
            try:
                body.prop(src, "size", text="Size")
            except (TypeError, AttributeError):
                pass
            try:
                body.prop(brush, "strength", text="Strength")
            except (TypeError, AttributeError):
                pass
        r = body.row()
        r.alert = True
        r.scale_y = 1.3
        r.operator("popup.done_painting", icon="CHECKMARK")
    row = body.row(align=True)
    row.operator("popup.trace_holes", text="Cut Painted Holes", icon="MOD_BOOLEAN")
    row.operator("popup.trace_holes", text="", icon="X").clear = True
    body.prop(st, "auto_holes")


def _brush_sections(lay, context):
    """While painting: Blender's colour and brush settings, right here."""
    sc = context.scene
    ip = sc.tool_settings.image_paint
    brush = getattr(ip, "brush", None)
    try:
        from bl_ui.properties_paint_common import UnifiedPaintPanel as U
    except ImportError:
        U = None
    sections = [("popup_paint_colour", "Colour", "COLOR"), ("popup_paint_brush", "Brush",
                                                             "BRUSH_DATA")]
    for key, title, icon in sections:
        head, body = lay.panel(key, default_closed=key != "popup_paint_colour")
        head.label(text=title, icon=icon)
        if body is None:
            continue
        try:
            if key == "popup_paint_colour":
                if U is not None and brush is not None:
                    U.prop_unified_color_picker(body, context, brush, "color", value_slider=True)
                    U.prop_unified_color(body, context, brush, "color", text="")
                    if sc.popup.colour_history is not None:
                        body.label(text="Colour History")
                        body.template_palette(sc.popup, "colour_history")
            elif key == "popup_paint_brush":
                if U is not None and brush is not None:
                    U.prop_unified(body, context, brush, "size", unified_name="use_unified_size",
                                   pressure_name="use_pressure_size", text="Size", slider=True)
                    U.prop_unified(body, context, brush, "strength",
                                   unified_name="use_unified_strength",
                                   pressure_name="use_pressure_strength", text="Strength",
                                   slider=True)
                    body.prop(brush, "blend", text="Blend")
        except Exception as ex:  # never break the panel
            body.label(text=f"Couldn't show this here ({type(ex).__name__})", icon="ERROR")


def _ink_colour(lay, context):
    """While drawing: what colour the strokes are, right here. A colour of
    their own (Colour) or one of the inks (materials) on Pop-up Sketch."""
    ts = context.tool_settings
    gpp = getattr(ts, "gpencil_paint", None)
    obj = context.view_layer.objects.active if context.view_layer else None
    if gpp is None or obj is None or obj.type != "GREASEPENCIL":
        return
    box = lay.box()
    try:
        from bl_ui.properties_paint_common import UnifiedPaintPanel as U
    except ImportError:
        U = None
    row = box.row(align=True)
    row.prop(gpp, "color_mode", expand=True)
    brush = gpp.brush
    if gpp.color_mode == "VERTEXCOLOR":
        if brush is not None:
            # as Blender's own Colour panel has it: Draw mode's colour is the
            # brush's own (the shared "unified" colour is for the other modes)
            ups = getattr(gpp, "unified_paint_settings", None)
            owner = brush if context.mode == "PAINT_GREASE_PENCIL" or ups is None \
                or not ups.use_unified_color else ups
            box.template_color_picker(owner, "color", value_slider=True)
            row = box.row(align=True)
            row.prop(owner, "color", text="")
            row.prop(owner, "secondary_color", text="")
            row.operator("paint.brush_colors_flip", icon="FILE_REFRESH", text="")
            gs = getattr(brush, "gpencil_settings", None)
            if gs is not None and getattr(brush, "gpencil_brush_type", "") in ("DRAW", "FILL"):
                box.prop(gs, "vertex_color_factor", slider=True, text="Mix Factor")
            _palettes(box, context, gpp)
    else:
        row = box.row()
        row.template_list("GPENCIL_UL_matslots", "", obj, "material_slots", obj,
                          "active_material_index", rows=3)
        row.operator("popup.ink_new", text="", icon="ADD")
        ma = obj.active_material
        g = getattr(ma, "grease_pencil", None) if ma is not None else None
        if g is not None:
            r = box.row(align=True)
            r.prop(g, "color", text="Line")
            r.prop(g, "show_fill", text="", icon="SNAP_FACE")
            if g.show_fill:
                r.prop(g, "fill_color", text="")
    if U is not None and brush is not None:
        try:
            U.prop_unified(box, context, brush, "size", unified_name="use_unified_size",
                           pressure_name="use_pressure_size", text="Size", slider=True)
            U.prop_unified(box, context, brush, "strength",
                           unified_name="use_unified_strength",
                           pressure_name="use_pressure_strength", text="Strength", slider=True)
        except Exception:  # (brush settings differ between versions: never break the panel)
            pass


def _palettes(box, context, gpp):
    """The colours used lately (noted as strokes go on the paper), and a
    palette of your own: click a swatch to draw with it."""
    recent = context.scene.popup.colour_history
    box.label(text="Used lately:")
    if recent is not None and len(recent.colors):
        box.template_palette(context.scene.popup, "colour_history")
    else:
        r = box.row()
        r.enabled = False
        r.label(text="Colours you draw with show here")
    box.label(text="Palette:")
    box.template_ID(gpp, "palette", new="palette.new")
    if gpp.palette is None:
        r = box.row()
        r.enabled = False
        r.label(text="Pick a palette, or New for one of your own")
    elif gpp.palette != recent:
        box.template_palette(gpp, "palette")


def _header_done(self, context):
    """While drawing or painting on the card, its controls and a Done button
    in the 3D view's header."""
    st = context.scene.popup
    if getattr(st, "plan_view", False):  # in the header too, while it's on
        row = self.layout.row()
        row.alert = True
        row.prop(st, "plan_view", text="Turn Off Plan View", icon="CANCEL", toggle=True)
    if _drawing(context):
        row = self.layout.row(align=True)
        from .ops import drawing_anywhere
        if drawing_anywhere(context):
            row.operator("popup.ink_paper", text="", icon="TEXTURE")
        r = row.row(align=True)
        r.alert = True
        r.operator("popup.done_drawing", icon="CHECKMARK")
    elif _painting(context):  # (Texture Paint, left on from before)
        row = self.layout.row()
        row.alert = True
        row.operator("popup.done_painting", icon="CHECKMARK")


def register():
    for c in classes:
        bpy.utils.register_class(c)
    bpy.types.VIEW3D_HT_header.append(_header_done)


def unregister():
    bpy.types.VIEW3D_HT_header.remove(_header_done)
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
