"""Part materials: one part of the card (a V-fold half, a box's top, a page)
rendered with its own material, e.g. metallic lettering or a glowing window.

Each face of the card carries its panel's number (pop_panel); parts are
kept by panel name, which survives rebuilds. A Geometry Nodes modifier
between the rig and Solid Paper sets each listed part's material (remade
on every rebuild with the current numbers), so nothing about
the card's mesh, art or rig changes and a rebuild keeps it. A new part
material starts as a copy of the paper material, so the art comes with it."""

import bpy
from bpy.props import EnumProperty, IntProperty, PointerProperty, StringProperty

from . import live
from .naming import N

MOD = "Pop-up Part Materials"

LOOKS = [
    ("PLAIN", "Paper", "The card's own paper and art, ready for your own shader settings"),
    ("METALLIC", "Metallic", "The art as polished metal foil (Metallic 1, low roughness)"),
    ("GLOSSY", "Glossy", "The art under a clear glossy coat"),
    ("GLOW", "Glow", "The art lit from within (emission), for windows, lamps and stars"),
]


def _rebuild_mod(self, context):
    apply(context.scene)


class PopupPartMaterial(bpy.types.PropertyGroup):
    panel: StringProperty(name="Part", description="The panel this material goes on")
    material: PointerProperty(type=bpy.types.Material, name="Material",
                              description="What this part renders with. Edit it in the "
                              "Shader Editor or the Material properties",
                              update=_rebuild_mod)


def _mech_of(panel):
    """A whole mechanism's entry: its panels' shared name prefix + ".*"."""
    return panel.split(".")[0] + ".*"


def _parts(scene, panel):
    """Vertex groups an entry covers: one part, or a whole mechanism's
    parts (not its glue tabs, which show the paper they glue to)."""
    if not panel.endswith(".*"):
        return [panel]
    m = live.meta(scene.popup.rig)
    pre = panel[:-1]
    return [p["name"] for p in (m["panels"] if m else [])
            if p["name"].startswith(pre) and p["kind"] != "tab"]


def _label(scene, panel):
    m = live.meta(scene.popup.rig)
    if panel.endswith(".*"):
        parts = _parts(scene, panel)
        if parts and m:
            lab = next(p["label"] for p in m["panels"] if p["name"] == parts[0])
            return lab.split(":")[0] + " (all of it)"
        return f"{panel[:-2]} (not on the card)"
    if m:
        for p in m["panels"]:
            if p["name"] == panel:
                return p["label"]
    return f"{panel} (not on the card)"


def _move_after_rig(card, mod):
    names = [m.name for m in card.modifiers]
    rig = next((i for i, m in enumerate(card.modifiers) if m.type == "ARMATURE"), -1)
    want = rig + 1
    i = names.index(mod.name)
    if i != want:
        card.modifiers.move(i, want)


def _int_inputs(cmp):
    """A Compare node's integer A and B sockets (their place in the socket
    list differs between Blender versions)."""
    ins = {i.identifier: i for i in cmp.inputs}
    if "A_INT" in ins:
        return ins["A_INT"], ins["B_INT"]
    vis = [i for i in cmp.inputs if i.enabled]
    return vis[0], vis[1]


def apply(scene):
    """(Re)make the modifier that sets each part's material."""
    st = scene.popup
    card = st.card
    if card is None:
        return
    # whole mechanisms first, so a single part's own material wins over them
    items = [(part, it.material)
             for it in sorted(st.part_materials, key=lambda i: not i.panel.endswith(".*"))
             if it.panel and it.material is not None
             for part in _parts(scene, it.panel)]
    mod = card.modifiers.get(MOD)
    if not items:
        if mod is not None:
            card.modifiers.remove(mod)
        return
    name = N(scene, MOD)
    ng = bpy.data.node_groups.get(name)
    if ng is None or ng.bl_idname != "GeometryNodeTree":
        ng = bpy.data.node_groups.new(name, "GeometryNodeTree")
        ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
        ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    ng.nodes.clear()
    gi = ng.nodes.new("NodeGroupInput")
    go = ng.nodes.new("NodeGroupOutput")
    gi.location = (-300, 0)
    sock = gi.outputs[0]
    x = 0
    meta = live.meta(st.rig)
    index = {p["name"]: i for i, p in enumerate(meta["panels"])} if meta else {}
    for panel, mat in items:
        if panel not in index:
            continue
        # each face knows its panel (pop_panel); vertices on a fold are
        # shared by the panels either side, so vertex groups won't do
        na = ng.nodes.new("GeometryNodeInputNamedAttribute")
        na.data_type = "INT"
        na.inputs["Name"].default_value = "pop_panel"
        na.location = (x - 200, -220)
        sm = ng.nodes.new("GeometryNodeSetMaterial")
        sm.inputs["Material"].default_value = mat
        sm.location = (x, 0)
        sm.label = panel
        cmp = ng.nodes.new("FunctionNodeCompare")
        cmp.data_type = "INT"
        cmp.operation = "EQUAL"
        a_in, b_in = _int_inputs(cmp)
        b_in.default_value = index[panel]
        cmp.location = (x - 100, -160)
        ng.links.new(na.outputs["Attribute"], a_in)
        ng.links.new(cmp.outputs[0], sm.inputs["Selection"])
        ng.links.new(sock, sm.inputs["Geometry"])
        sock = sm.outputs["Geometry"]
        x += 260
    go.location = (x, 0)
    ng.links.new(sock, go.inputs[0])
    if mod is None:
        mod = card.modifiers.new(MOD, "NODES")
    mod.node_group = ng
    mod.show_in_editmode = False
    _move_after_rig(card, mod)


def _bsdf(mat):
    return next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)


def new_material(scene, panel, look):
    base = bpy.data.materials.get(N(scene, "Pop-up Paper"))
    label = _label(scene, panel).replace(":", "")
    look_name = dict((k, v) for k, v, _ in LOOKS)[look]
    if base is not None:
        mat = base.copy()
        mat.name = f"{label} ({look_name})"
    else:
        mat = bpy.data.materials.new(f"{label} ({look_name})")
        mat.use_nodes = True
    nt = mat.node_tree
    bsdf = _bsdf(mat)
    out = next((n for n in nt.nodes if n.type == "OUTPUT_MATERIAL" and n.is_active_output),
               None)
    if bsdf is not None and out is not None:
        from .colours import MIX
        links = out.inputs["Surface"].links
        if links and links[0].from_node.name == MIX:
            # copied while True Colours had the paper unlit: render it lit
            nt.links.new(bsdf.outputs[0], out.inputs["Surface"])
    if bsdf is not None:
        ins = bsdf.inputs
        if look in ("METALLIC", "GLOSSY"):
            # the whole part shines: not just its metallic images
            for k in ("Metallic", "Roughness"):
                for ln in list(ins[k].links):
                    nt.links.remove(ln)
        if look == "METALLIC":
            ins["Metallic"].default_value = 1.0
            ins["Roughness"].default_value = 0.22
        elif look == "GLOSSY":
            ins["Roughness"].default_value = 0.35
            if ins.get("Coat Weight") is not None:
                ins["Coat Weight"].default_value = 1.0
                ins["Coat Roughness"].default_value = 0.05
        elif look == "GLOW":
            src = ins["Base Color"].links[0].from_socket if ins["Base Color"].links else None
            if src is not None:
                nt.links.new(src, ins["Emission Color"])
            else:
                ins["Emission Color"].default_value = ins["Base Color"].default_value
            ins["Emission Strength"].default_value = 2.0
    mat["pop_part_look"] = look
    return mat


class POPUP_OT_part_material(bpy.types.Operator):
    """Render the picked part with its own material, starting from the paper
    and its art, so it can be metallic, glossy or glow while the rest of the
    card stays paper. Rebuilding keeps it"""
    bl_idname = "popup.part_material"
    bl_label = "Give This Part Its Own Material"
    bl_options = {"REGISTER", "UNDO"}

    look: EnumProperty(name="Look", items=LOOKS, default="METALLIC")

    def execute(self, context):
        sc = context.scene
        st = sc.popup
        panel = st.material_part
        if not panel or panel == "NONE":
            self.report({"ERROR"}, "Build the card and pick a part first")
            return {"CANCELLED"}
        if st.material_whole and not panel.startswith("Page."):
            panel = _mech_of(panel)
        it = next((i for i in st.part_materials if i.panel == panel), None)
        if it is None:
            it = st.part_materials.add()
            it.panel = panel
        it.material = new_material(sc, panel, self.look)
        st.part_material_index = list(st.part_materials).index(it)
        apply(sc)
        return {"FINISHED"}


class POPUP_OT_part_material_remove(bpy.types.Operator):
    """Put this part back to the card's own paper (the material itself is
    kept in the file until it's unused)"""
    bl_idname = "popup.part_material_remove"
    bl_label = "Back to Paper"
    bl_options = {"REGISTER", "UNDO"}

    index: IntProperty(default=-1)

    def execute(self, context):
        st = context.scene.popup
        i = self.index if self.index >= 0 else st.part_material_index
        if 0 <= i < len(st.part_materials):
            st.part_materials.remove(i)
            st.part_material_index = min(i, len(st.part_materials) - 1)
        apply(context.scene)
        return {"FINISHED"}


class POPUP_UL_part_materials(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        row = layout.row(align=True)
        row.label(text=_label(context.scene, item.panel), icon="MATERIAL")
        row.prop(item, "material", text="")


def draw(layout, context):
    st = context.scene.popup
    col = layout.column(align=True)
    col.label(text="Part Materials (render)")
    col.prop(st, "material_part", text="")
    row = col.row(align=True)
    row.operator_menu_enum("popup.part_material", "look", text="Own Material",
                           icon="MATERIAL")
    row.prop(st, "material_whole", text="", icon="LINKED")
    if len(st.part_materials):
        col.template_list("POPUP_UL_part_materials", "", st, "part_materials", st,
                          "part_material_index", rows=2)
        it = st.part_materials[st.part_material_index] \
            if 0 <= st.part_material_index < len(st.part_materials) else None
        if it is not None and it.material is not None:
            bsdf = _bsdf(it.material) if it.material.use_nodes else None
            if bsdf is not None:
                b = col.box().column(align=True)
                for k in ("Metallic", "Roughness", "Coat Weight", "Emission Strength"):
                    if bsdf.inputs.get(k) is not None:
                        b.prop(bsdf.inputs[k], "default_value", text=k)
            col.operator("popup.part_material_remove", icon="X")


classes = (POPUP_OT_part_material, POPUP_OT_part_material_remove, POPUP_UL_part_materials)


def register():
    for c in classes:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
