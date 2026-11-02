"""True colours while painting.

What the viewport shows is the paint after lighting and the scene's view
transform (AgX by default, which dulls bright, saturated colours). Picking a
colour off the screen (the colour picker's eyedropper, or sampling) then
reads back a darker, duller colour than the one painted, and each re-sample
drifts further. While in Texture Paint on a pop-up card this:

* switches the scene's view transform to Standard,
* shows the paper unlit: in EEVEE / Material Preview the paper material's
  output is switched to its art colour as emission (holes stay see-through);
  3D views in Solid mode show flat texture colours,

so what you see (and sample) is what is in the art, and what prints. All of
it is put back on leaving Texture Paint.
"""

import json

import bpy

KEY = "pop_true_colours"
EMIT, MIX, CLEAR = "Pop-up True Colour", "Pop-up True Mix", "Pop-up True Clear"


def _views():
    for wi, win in enumerate(bpy.context.window_manager.windows):
        for ai, area in enumerate(win.screen.areas):
            if area.type == "VIEW_3D":
                yield f"{wi}:{ai}", area.spaces.active.shading


def _paper(scene):
    st = scene.popup
    if st.card is None or not st.card.data.materials:
        return None
    mat = st.card.data.materials[0]
    return mat if mat is not None and mat.use_nodes else None


def _unlit(mat):
    """Point the material output at the art colour as emission. Returns the
    socket the output was fed from, to put back."""
    nt = mat.node_tree
    out = next((n for n in nt.nodes if n.type == "OUTPUT_MATERIAL" and n.is_active_output),
               None)
    bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if out is None or bsdf is None:
        return None
    was = out.inputs["Surface"].links[0].from_socket if out.inputs["Surface"].links else None
    if was is not None and was.node != bsdf:
        # something else draws the paper (paint layers, your own nodes): leave the material alone, or its layers would vanish
        # while painting; the flat, texture-coloured Solid view still shows
        # true colours
        return None
    emit = nt.nodes.get(EMIT) or nt.nodes.new("ShaderNodeEmission")
    emit.name = emit.label = EMIT
    mix = nt.nodes.get(MIX) or nt.nodes.new("ShaderNodeMixShader")
    mix.name = mix.label = MIX
    clear = nt.nodes.get(CLEAR) or nt.nodes.new("ShaderNodeBsdfTransparent")
    clear.name = clear.label = CLEAR
    for i, n in enumerate((emit, clear, mix)):
        n.location = out.location.x - 200, out.location.y - 220 - 120 * i
    base = bsdf.inputs["Base Color"]
    if base.links:
        nt.links.new(base.links[0].from_socket, emit.inputs["Color"])
    else:
        emit.inputs["Color"].default_value = base.default_value
    emit.inputs["Strength"].default_value = 1.0
    alpha = bsdf.inputs["Alpha"]
    if alpha.links:
        nt.links.new(alpha.links[0].from_socket, mix.inputs["Fac"])
    else:
        mix.inputs["Fac"].default_value = alpha.default_value
    nt.links.new(clear.outputs[0], mix.inputs[1])
    nt.links.new(emit.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])
    return was


def _relit(mat, was):
    nt = mat.node_tree
    out = next((n for n in nt.nodes if n.type == "OUTPUT_MATERIAL" and n.is_active_output),
               None)
    links = out.inputs["Surface"].links if out is not None else ()
    bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
    lit = was if was is not None else (bsdf.outputs[0] if bsdf is not None else None)
    if lit is not None and links and links[0].from_node.name == MIX:
        nt.links.new(lit, out.inputs["Surface"])
    ours = {nt.nodes.get(k) for k in (EMIT, MIX, CLEAR)} - {None}
    # Anything else that came to take the unlit preview as its paper (a
    # paint layer stack set up while painting) gets the real, lit
    # paper instead: the flat colours are only ever a painting preview.
    for n in ours:
        for o in n.outputs:
            for ln in list(o.links):
                if ln.to_node not in ours and ln.to_node != out and lit is not None:
                    nt.links.new(lit, ln.to_socket)
    for n in ours:
        nt.nodes.remove(n)


def heal(scene):
    """Not painting, yet the unlit preview is still in the paper (left by a
    session that ended oddly, or caught up in a layer stack): put the lit
    paper back."""
    if KEY in scene:
        return False
    mat = _paper(scene)
    if mat is None or mat.node_tree is None:
        return False
    if not any(mat.node_tree.nodes.get(k) for k in (EMIT, MIX, CLEAR)):
        return False
    _relit(mat, None)
    return True


def enter(scene):
    st = scene.popup
    if not st.true_colours or st.card is None or KEY in scene:
        return False
    vs = scene.view_settings
    saved = dict(view=vs.view_transform, look=vs.look, shading={}, out=None)
    for key, sh in _views():
        if sh.type == "SOLID":
            saved["shading"][key] = (sh.light, sh.color_type)
            sh.light = "FLAT"
            sh.color_type = "TEXTURE"
    mat = _paper(scene)
    if mat is not None:
        was = _unlit(mat)
        if was is not None:
            saved["out"] = [mat.name, was.node.name, was.identifier]
    scene[KEY] = json.dumps(saved)
    try:
        vs.view_transform = "Standard"
        vs.look = "None"
    except TypeError:
        pass
    return True


def leave(scene):
    raw = scene.get(KEY)
    if raw is None:
        return
    del scene[KEY]
    try:
        saved = json.loads(raw)
    except ValueError:
        return
    vs = scene.view_settings
    try:
        vs.view_transform = saved["view"]
        vs.look = saved["look"]
    except (TypeError, KeyError):
        pass
    for key, sh in _views():
        old = saved.get("shading", {}).get(key)
        if old is None or sh.type != "SOLID":
            continue
        try:
            sh.light, sh.color_type = old
        except TypeError:
            pass
    out = saved.get("out")
    mat = bpy.data.materials.get(out[0]) if out else _paper(scene)
    if mat is not None and mat.use_nodes:
        was = None
        if out:
            node = mat.node_tree.nodes.get(out[1])
            if node is not None:
                was = next((s for s in node.outputs if s.identifier == out[2]), None)
        _relit(mat, was)
