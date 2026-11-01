"""Plan view: look straight into the card (or a carousel stage) part open,
with everything squashed flat along the view and drawn see-through, each
mechanism (or panel) in its own colour, so overlaps in a busy build show as
darker patches. Viewport only: the modifier never renders, and turning it
off puts the view, the shading and the opening back as they were."""

import json
import math

import bpy
from mathutils import Matrix, Vector

from .core.geom import rot_y
from .naming import N

MOD = "Pop-up Plan View"
SAVED = "pop_plan_saved"
N_COL = 12
# strong, well-spread colours: neighbours in the list (made one after the
# other, so usually close together on the card) never look alike
PALETTE = [(0.95, 0.30, 0.25), (0.20, 0.55, 0.95), (0.98, 0.75, 0.15), (0.30, 0.80, 0.40),
           (0.75, 0.35, 0.90), (0.10, 0.80, 0.80), (0.95, 0.50, 0.75), (0.55, 0.45, 0.20),
           (0.40, 0.30, 0.95), (0.65, 0.85, 0.20), (0.95, 0.55, 0.10), (0.25, 0.45, 0.45)]


def _materials():
    out = []
    for k, c in enumerate(PALETTE):
        name = f"Pop-up Plan {k + 1:02d}"
        mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
        mat.diffuse_color = (*c, 1.0)
        out.append(mat)
    return out


def tmax(scene):
    st = scene.popup
    master = st.stage_master
    if master is not None and master != scene:
        return 360.0 / master.popup.stage_count
    return 180.0


def hold(scene):
    st = scene.popup
    if st.stage_master is not None and st.stage_master != scene:
        return "SYM"
    return st.hold


def current_open(scene):
    st = scene.popup
    if st.stage_master is not None:
        from . import carousel
        v = carousel.open_value(scene)
        return None if v is None else float(v) / st.stage_master.popup.stage_count
    rig = st.rig
    return float(rig.get("pop_open", 90.0)) if rig is not None else None


def set_open(scene, t):
    st = scene.popup
    if st.stage_master is not None:
        from . import carousel
        carousel.set_open(scene, t * st.stage_master.popup.stage_count)
    elif st.rig is not None:
        st.rig["pop_open"] = t
        st.rig.update_tag()


def view_axis(hold_, t):
    """Model-space direction from the spine out into the open card, halfway
    between the pages (straight down onto a flat card)."""
    b = math.radians(180.0 - t)
    gl, gr = {"SYM": (0.5 * b, 0.5 * b), "LEFT": (0.0, b)}.get(hold_, (b, 0.0))
    l = rot_y(gl).to_3x3() @ Vector((-1.0, 0.0, 0.0))
    r = rot_y(-gr).to_3x3() @ Vector((1.0, 0.0, 0.0))
    v = l + r
    if v.length < 1e-6:
        return (rot_y(-gr).to_3x3() @ Vector((0.0, 0.0, 1.0))).normalized()
    return v.normalized()


def angle(scene):
    st = scene.popup
    t = current_open(scene) if st.plan_use_open else st.plan_angle
    t = 0.5 * tmax(scene) if t is None else t
    return max(0.5, min(tmax(scene), t))


def _tree(scene, axis, keep, by):
    name = N(scene, MOD)
    ng = bpy.data.node_groups.get(name)
    if ng is not None and ng.get("pop_by") == by and "Axis" in ng.nodes and \
            "Squash" in ng.nodes:  # only turned, or squashed more or less
        ng.nodes["Axis"].vector = axis
        ng.nodes["Squash"].inputs[1].default_value = -(1.0 - keep)
        return ng
    if ng is None or ng.bl_idname != "GeometryNodeTree":
        ng = bpy.data.node_groups.new(name, "GeometryNodeTree")
        ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
        ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    ng.nodes.clear()
    nodes, links = ng.nodes, ng.links
    gi, go = nodes.new("NodeGroupInput"), nodes.new("NodeGroupOutput")
    gi.location = (-900, 0)
    # squash along the axis: p - axis (p . axis)(1 - keep); the spine runs
    # through the origin, so it stays put
    pos = nodes.new("GeometryNodeInputPosition")
    pos.location = (-900, -250)
    ax = nodes.new("FunctionNodeInputVector")
    ax.name = "Axis"
    ax.vector = axis
    ax.location = (-900, -380)
    dot = nodes.new("ShaderNodeVectorMath")
    dot.operation = "DOT_PRODUCT"
    dot.location = (-700, -300)
    links.new(pos.outputs[0], dot.inputs[0])
    links.new(ax.outputs[0], dot.inputs[1])
    mul = nodes.new("ShaderNodeMath")
    mul.operation = "MULTIPLY"
    mul.name = "Squash"
    mul.inputs[1].default_value = -(1.0 - keep)
    mul.location = (-520, -300)
    links.new(dot.outputs["Value"], mul.inputs[0])
    sc_ = nodes.new("ShaderNodeVectorMath")
    sc_.operation = "SCALE"
    sc_.location = (-340, -300)
    links.new(ax.outputs[0], sc_.inputs[0])
    links.new(mul.outputs[0], sc_.inputs["Scale"])
    sp = nodes.new("GeometryNodeSetPosition")
    sp.location = (-160, 0)
    links.new(gi.outputs[0], sp.inputs["Geometry"])
    links.new(sc_.outputs[0], sp.inputs["Offset"])
    sock = sp.outputs[0]
    # colours: each mechanism (or panel) one of N_COL
    mats = _materials()
    key = nodes.new("GeometryNodeInputNamedAttribute")
    key.data_type = "INT"
    key.inputs["Name"].default_value = "pop_mech" if by == "MECH" else "pop_panel"
    key.location = (-520, -600)
    mod_ = nodes.new("ShaderNodeMath")
    mod_.operation = "FLOORED_MODULO"
    mod_.inputs[1].default_value = float(N_COL)
    mod_.location = (-340, -600)
    links.new(key.outputs["Attribute"], mod_.inputs[0])
    x = 40
    for k, mat in enumerate(mats):
        cmp = nodes.new("FunctionNodeCompare")
        cmp.data_type = "FLOAT"
        cmp.operation = "EQUAL"
        cmp.inputs["Epsilon"].default_value = 0.1
        cmp.inputs["B"].default_value = float(k)
        cmp.location = (x - 120, -220)
        links.new(mod_.outputs[0], cmp.inputs["A"])
        sm = nodes.new("GeometryNodeSetMaterial")
        sm.inputs["Material"].default_value = mat
        sm.location = (x, 0)
        links.new(sock, sm.inputs["Geometry"])
        links.new(cmp.outputs[0], sm.inputs["Selection"])
        sock = sm.outputs[0]
        x += 200
    card = nodes.new("GeometryNodeInputNamedAttribute")
    card.data_type = "INT"
    card.inputs["Name"].default_value = "pop_mech"
    card.location = (x - 300, -420)
    is0 = nodes.new("FunctionNodeCompare")
    is0.data_type = "INT"
    is0.operation = "EQUAL"
    is0.location = (x - 120, -420)
    from .materials import _int_inputs
    a_in, b_in = _int_inputs(is0)
    links.new(card.outputs["Attribute"], a_in)
    b_in.default_value = 0
    # the card's own pages as outlines only: tinted they'd wash every
    # mechanism behind (or in front of) them out
    sm = nodes.new("GeometryNodeDeleteGeometry")
    sm.domain = "FACE"
    sm.mode = "ONLY_FACE"
    sm.location = (x, 0)
    links.new(sock, sm.inputs["Geometry"])
    links.new(is0.outputs[0], sm.inputs["Selection"])
    go.location = (x + 220, 0)
    links.new(sm.outputs[0], go.inputs[0])
    ng["pop_by"] = by
    return ng


def _views(context):
    """3D views on screen (none in the background)."""
    out = []
    win = getattr(context, "window", None)
    screens = [win.screen] if win is not None and win.screen else []
    if not screens and context.window_manager:
        screens = [w.screen for w in context.window_manager.windows]
    for scr in screens:
        for i, area in enumerate(scr.areas):
            if area.type == "VIEW_3D":
                out.append((f"{scr.name}:{i}", area, area.spaces.active))
    return out


def _save(scene, context):
    sh = []
    for key, area, sp in _views(context):
        r3d, s = sp.region_3d, sp.shading
        sh.append(dict(key=key, rot=list(r3d.view_rotation), loc=list(r3d.view_location),
                       dist=r3d.view_distance, persp=r3d.view_perspective,
                       type=s.type, color=s.color_type, light=s.light, xray=s.show_xray,
                       alpha=s.xray_alpha, cull=s.show_backface_culling))
    scene[SAVED] = json.dumps(dict(open=current_open(scene), views=sh))


def _restore(scene, context):
    raw = scene.get(SAVED)
    if raw is None:
        return
    try:
        saved = json.loads(raw)
    except ValueError:
        saved = {}
    if saved.get("open") is not None:
        set_open(scene, float(saved["open"]))
    views = {v["key"]: v for v in saved.get("views", [])}
    for key, area, sp in _views(context):
        v = views.get(key)
        if v is None:
            continue
        r3d, s = sp.region_3d, sp.shading
        r3d.view_rotation = v["rot"]
        r3d.view_location = v["loc"]
        r3d.view_distance = v["dist"]
        r3d.view_perspective = v["persp"]
        s.type = v["type"]
        s.color_type = v["color"]
        s.light = v["light"]
        s.show_xray = v["xray"]
        s.xray_alpha = v["alpha"]
        s.show_backface_culling = v["cull"]
        area.tag_redraw()
    del scene[SAVED]


def _aim(scene, context, axis, turn_only=False):
    """Look straight down the axis, orthographic, the whole card in view
    (turn_only: keep where they've panned and zoomed to)."""
    st = scene.popup
    card = st.card
    W, H = st.card_dict()["W"], st.card_dict()["H"]
    s = 1.0 / st.mm_per_unit
    M = card.matrix_world
    z = (M.to_3x3() @ axis).normalized()
    y = (M.to_3x3() @ Vector((0.0, 1.0, 0.0))).normalized()
    y = (y - z * y.dot(z)).normalized()
    x = y.cross(z)
    rot = Matrix((x, y, z)).transposed().to_quaternion()
    centre = M @ Vector((0.0, 0.5 * H * s, 0.0))
    # the open card's span across the view, and its height
    reach = max(W * s, 0.5 * H * s) * 1.25 * M.to_scale()[0]
    for key, area, sp in _views(context):
        r3d, sh = sp.region_3d, sp.shading
        r3d.view_rotation = rot
        if turn_only:
            area.tag_redraw()
            continue
        r3d.view_location = centre
        r3d.view_distance = reach * 1.6
        r3d.view_perspective = "ORTHO"
        sh.type = "SOLID"
        sh.color_type = "MATERIAL"
        sh.light = "FLAT"
        sh.show_xray = True
        sh.xray_alpha = st.plan_alpha
        sh.show_backface_culling = False
        area.tag_redraw()


def refresh(scene, context=None, aim=False):
    """Put the plan view's modifier (last on the card) and opening in step
    with the settings; turn it off when the switch is off."""
    context = context or bpy.context
    st = scene.popup
    card = st.card
    if card is None:
        return
    mod = card.modifiers.get(MOD)
    if not st.plan_view:
        if mod is not None:
            card.modifiers.remove(mod)
        return
    t = angle(scene)
    if not st.plan_use_open:
        set_open(scene, t)
    axis = view_axis(hold(scene), t)
    ng = _tree(scene, axis, st.plan_depth, st.plan_colour)
    if mod is None:
        mod = card.modifiers.new(MOD, "NODES")
    mod.node_group = ng
    mod.show_render = False
    mod.show_viewport = True
    mod.show_in_editmode = False
    # last, after the rig, the paper's thickness and part materials
    i = card.modifiers.find(mod.name)
    if i != len(card.modifiers) - 1:
        card.modifiers.move(i, len(card.modifiers) - 1)
    card.update_tag()
    scene["pop_plan_t"] = t
    if aim:
        _aim(scene, context, axis, turn_only=aim == "TURN")


def toggle(scene, context, on):
    if on:
        if SAVED not in scene:
            _save(scene, context)
        refresh(scene, context, aim=True)
    else:
        refresh(scene, context)
        _restore(scene, context)


def on_rebuild(scene):
    """A rebuild may add modifiers after it: keep it last."""
    if scene.popup.plan_view and scene.popup.card is not None:
        refresh(scene)


def changed(self, context):
    """A plan-view setting changed."""
    sc = self.id_data
    if not self.plan_view:
        return
    refresh(sc, context, aim="TURN")
    for key, area, sp in _views(context):
        sp.shading.xray_alpha = self.plan_alpha
        area.tag_redraw()


def switched(self, context):
    toggle(self.id_data, context, self.plan_view)


@bpy.app.handlers.persistent
def _follow_open(scene, depsgraph=None):
    """Following the card's own Open: turn with it as it is scrubbed."""
    st = getattr(scene, "popup", None)
    if st is None or not st.plan_view or not st.plan_use_open:
        return
    t = angle(scene)
    if abs(t - float(scene.get("pop_plan_t", -1.0))) > 0.25:
        refresh(scene, aim="TURN")


def register():
    if _follow_open not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(_follow_open)
    if _follow_open not in bpy.app.handlers.frame_change_post:
        bpy.app.handlers.frame_change_post.append(_follow_open)


def unregister():
    for hs in (bpy.app.handlers.depsgraph_update_post, bpy.app.handlers.frame_change_post):
        if _follow_open in hs:
            hs.remove(_follow_open)
