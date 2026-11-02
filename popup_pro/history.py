"""Colour history while painting the card.

Notes the brush colour whenever a stroke lands on the card's paper (or a
paint layer on it), newest first, each colour once, in a palette shown under
Colour while painting."""

import bpy


OWN = "Pop-up Colour History"
KEEP = 20


def _brush_color(context):
    ts = context.tool_settings
    ip = ts.image_paint
    ups = getattr(ts, "unified_paint_settings", None) or getattr(ip, "unified_paint_settings",
                                                                 None)
    brush = ip.brush
    owner = ups if (ups is not None and ups.use_unified_color) or brush is None else brush
    return tuple(owner.color)


def palette(scene, create=True):
    """Where colours are noted."""
    pal = bpy.data.palettes.get(OWN)
    if pal is None and create:
        pal = bpy.data.palettes.new(OWN)
    if pal is not None and scene.popup.colour_history != pal:
        scene.popup.colour_history = pal
    return pal


def note(scene, color):
    pal = palette(scene)
    if pal is None:
        return False
    if len(pal.colors) and all(abs(a - b) < 1e-3 for a, b in zip(pal.colors[0].color, color)):
        return False
    keep = [tuple(c.color) for c in pal.colors]
    pal.colors.clear()
    pal.colors.new().color = color[:3]
    for c in keep:
        if len(pal.colors) >= KEEP:
            break
        if all(abs(a - b) < 1e-3 for a, b in zip(c, color)):
            continue  # each colour once: it moves to the front
        pal.colors.new().color = c
    return True


@bpy.app.handlers.persistent
def _on_update(scene, depsgraph=None):
    try:
        if depsgraph is not None and not depsgraph.id_type_updated("IMAGE"):
            return
        context = bpy.context
        if context.mode != "PAINT_TEXTURE":
            return
        from .ops import painting, painting_into
        if not painting(context):
            return
        sc = context.scene
        img = painting_into(sc)
        if img is None or not img.is_dirty:
            return
        brush = context.tool_settings.image_paint.brush
        if brush is not None and getattr(brush, "blend", "") in ("ERASE_ALPHA", "ADD_ALPHA"):
            return  # erasing or restoring paper: no colour
        note(sc, _brush_color(context))
    except Exception as ex:  # never get in the way of painting
        print(f"Pop-Up Pro: colour history: {ex}")


def register():
    if _on_update not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(_on_update)


def unregister():
    if _on_update in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(_on_update)
