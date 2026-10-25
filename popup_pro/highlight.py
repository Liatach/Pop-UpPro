"""Highlight the mechanism selected in the Mechanisms list: a see-through
tint over its panels, on the folded card and on the flat layout. Drawn by the
viewport only (never in renders)."""

import re

import bpy
import gpu
from gpu_extras.batch import batch_for_shader

COLOUR = (1.0, 0.55, 0.1, 0.35)
_handle = None
_cache = {}
_UID = re.compile(r"^[A-Za-z]+?(\d+)[.a-z]")


def _uid_of(name):
    m = _UID.match(name)
    return int(m.group(1)) if m else None


def _panels(scene, uid):
    """Panel indices (pop_panel values) belonging to a mechanism."""
    import json
    rig = scene.popup.rig
    if rig is None:
        return set()
    try:
        meta = json.loads(rig.get("pop_meta", "{}"))
    except ValueError:
        return set()
    return {i for i, p in enumerate(meta.get("panels", [])) if _uid_of(p["name"]) == uid}


def _tris(obj, depsgraph, want):
    ev = obj.evaluated_get(depsgraph)
    me = ev.to_mesh()
    try:
        attr = me.attributes.get("pop_panel")
        if attr is None or attr.domain != "FACE":
            return []
        vals = [0] * len(me.polygons)
        attr.data.foreach_get("value", vals)
        me.calc_loop_triangles()
        M = obj.matrix_world
        out = []
        nudge = 0.0015
        for lt in me.loop_triangles:
            if vals[lt.polygon_index] in want:
                n = lt.normal
                for vi in lt.vertices:
                    out.append(M @ (me.vertices[vi].co + n * nudge))
        return out
    finally:
        ev.to_mesh_clear()


def draw():
    ctx = bpy.context
    sc = ctx.scene
    if sc is None or not hasattr(sc, "popup"):
        return
    st = sc.popup
    if not st.highlight or st.rig is None or not (0 <= st.active < len(st.mechs)):
        return
    if ctx.mode == "PAINT_TEXTURE":
        return  # keep the colours true while painting
    uid = st.mechs[st.active].uid
    want = _panels(sc, uid)
    if not want:
        return
    dg = ctx.evaluated_depsgraph_get()
    pts = []
    for obj in (st.card, st.layout):
        if obj is not None and obj.visible_get():
            pts += _tris(obj, dg, want)
    if not pts:
        return
    shader = gpu.shader.from_builtin("UNIFORM_COLOR")
    batch = batch_for_shader(shader, "TRIS", {"pos": [p[:] for p in pts]})
    gpu.state.blend_set("ALPHA")
    gpu.state.depth_test_set("LESS_EQUAL")
    gpu.state.depth_mask_set(False)
    shader.uniform_float("color", COLOUR)
    batch.draw(shader)
    gpu.state.depth_mask_set(True)
    gpu.state.depth_test_set("NONE")
    gpu.state.blend_set("NONE")


def register():
    global _handle
    if _handle is None and not bpy.app.background:
        _handle = bpy.types.SpaceView3D.draw_handler_add(draw, (), "WINDOW", "POST_VIEW")


def unregister():
    global _handle
    if _handle is not None:
        bpy.types.SpaceView3D.draw_handler_remove(_handle, "WINDOW")
        _handle = None
