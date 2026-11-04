"""Visibility per mechanism: Normal, Wire (outline only) or Hidden, on the
folded card and the flat layout. Viewport only (never renders or exports):
a Geometry Nodes modifier drops the faces of those mechanisms (by the
pop_mech face attribute), keeping a wire one's edges. Draw Anywhere paints
through them, onto whatever paper is behind."""

import bpy

from .naming import N

MOD = "Pop-up Visibility"
STATES = [("NORMAL", "Normal", "Shown as usual", "HIDE_OFF", 0),
          ("WIRE", "Wire", "Outline only: see and paint what's behind it", "SHADING_WIRE", 1),
          ("HIDDEN", "Hidden", "Not shown: see and paint what's behind it", "HIDE_ON", 2)]


def sets(st):
    """(uids shown as wire, uids hidden)"""
    wire = {m.uid for m in st.mechs if m.visibility == "WIRE"}
    hidden = {m.uid for m in st.mechs if m.visibility == "HIDDEN"}
    return wire, hidden


def see_through(st):
    """Mechanisms not drawn solid (Draw Anywhere passes them by)."""
    wire, hidden = sets(st)
    return wire | hidden


def _member(ng, attr, uids, x, y):
    """A Boolean socket: the face's pop_mech is one of uids."""
    from .materials import _int_inputs
    sock = None
    for k, u in enumerate(sorted(uids)):
        cmp = ng.nodes.new("FunctionNodeCompare")
        cmp.data_type = "INT"
        cmp.operation = "EQUAL"
        a_in, b_in = _int_inputs(cmp)
        ng.links.new(attr.outputs["Attribute"], a_in)
        b_in.default_value = u
        cmp.location = (x, y - 120 * k)
        if sock is None:
            sock = cmp.outputs[0]
        else:
            orr = ng.nodes.new("FunctionNodeBooleanMath")
            orr.operation = "OR"
            orr.location = (x + 180, y - 120 * k)
            ng.links.new(sock, orr.inputs[0])
            ng.links.new(cmp.outputs[0], orr.inputs[1])
            sock = orr.outputs[0]
    return sock


def _tree(scene, wire, hidden):
    name = N(scene, MOD)
    ng = bpy.data.node_groups.get(name)
    if ng is None or ng.bl_idname != "GeometryNodeTree":
        ng = bpy.data.node_groups.new(name, "GeometryNodeTree")
        ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
        ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    ng.nodes.clear()
    gi, go = ng.nodes.new("NodeGroupInput"), ng.nodes.new("NodeGroupOutput")
    gi.location = (-900, 0)
    attr = ng.nodes.new("GeometryNodeInputNamedAttribute")
    attr.data_type = "INT"
    attr.inputs["Name"].default_value = "pop_mech"
    attr.location = (-900, -300)
    sock = gi.outputs[0]
    x = -500
    if hidden:
        # hidden: the faces go, then the edges left with no face (the card
        # has no loose edges of its own)
        sel = _member(ng, attr, hidden, -700, -300)
        d1 = ng.nodes.new("GeometryNodeDeleteGeometry")
        d1.domain, d1.mode = "FACE", "ONLY_FACE"
        d1.location = (x, 0)
        ng.links.new(sock, d1.inputs["Geometry"])
        ng.links.new(sel, d1.inputs["Selection"])
        nb = ng.nodes.new("GeometryNodeInputMeshEdgeNeighbors")
        nb.location = (x, -300)
        z = ng.nodes.new("FunctionNodeCompare")
        z.data_type = "INT"
        z.operation = "EQUAL"
        from .materials import _int_inputs
        a_in, b_in = _int_inputs(z)
        ng.links.new(nb.outputs["Face Count"], a_in)
        b_in.default_value = 0
        z.location = (x + 180, -300)
        d2 = ng.nodes.new("GeometryNodeDeleteGeometry")
        d2.domain, d2.mode = "EDGE", "ALL"
        d2.location = (x + 360, 0)
        ng.links.new(d1.outputs[0], d2.inputs["Geometry"])
        ng.links.new(z.outputs[0], d2.inputs["Selection"])
        sock = d2.outputs[0]
        x += 600
    if wire:
        sel = _member(ng, attr, wire, x - 200, -700)
        d3 = ng.nodes.new("GeometryNodeDeleteGeometry")
        d3.domain, d3.mode = "FACE", "ONLY_FACE"
        d3.location = (x + 200, 0)
        ng.links.new(sock, d3.inputs["Geometry"])
        ng.links.new(sel, d3.inputs["Selection"])
        sock = d3.outputs[0]
        x += 400
    go.location = (x + 200, 0)
    ng.links.new(sock, go.inputs[0])
    return ng


def _place(obj, ng):
    mod = obj.modifiers.get(MOD)
    if ng is None:
        if mod is not None:
            obj.modifiers.remove(mod)
        return
    if mod is None:
        mod = obj.modifiers.new(MOD, "NODES")
    mod.node_group = ng
    mod.show_render = False
    mod.show_viewport = True
    mod.show_in_editmode = False
    # after everything else (the rig, the paper's thickness, materials),
    # but before the plan view, which stays last
    from .debug import MOD as PLAN
    want = len(obj.modifiers) - 1
    if PLAN in obj.modifiers and obj.modifiers.find(PLAN) > obj.modifiers.find(MOD):
        want = obj.modifiers.find(PLAN) - 1
    i = obj.modifiers.find(MOD)
    if i != want:
        obj.modifiers.move(i, want)
    obj.update_tag()


def refresh(scene):
    st = getattr(scene, "popup", None)
    if st is None:
        return
    wire, hidden = sets(st)
    ng = _tree(scene, wire, hidden) if (wire or hidden) else None
    for obj in (st.card, st.layout):
        if obj is not None and obj.name in bpy.data.objects:
            _place(obj, ng)
    if ng is None:
        old = bpy.data.node_groups.get(N(scene, MOD))
        if old is not None and old.users == 0:
            bpy.data.node_groups.remove(old)
