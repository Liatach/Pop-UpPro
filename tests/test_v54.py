"""v0.54: colour history notes the colours painted onto the card's paper
(Paint System's history only noted strokes on its own layers)."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
PS = os.environ.get("PAINT_SYSTEM_DIR")
if PS:
    sys.path.insert(0, PS)

import bpy  # noqa: E402

bpy.ops.wm.read_factory_settings(use_empty=True)
import popup_pro as addon  # noqa: E402
from popup_pro import history  # noqa: E402

addon.register()
sc = bpy.context.scene
st = sc.popup
bpy.ops.popup.build()
assert history._on_update in bpy.app.handlers.depsgraph_update_post
for c in ((1, 0, 0), (1, 0, 0), (0, 1, 0), (1, 0, 0)):
    history.note(sc, c)
pal = st.colour_history
assert pal is not None and pal.name == history.OWN
got = [tuple(round(x, 3) for x in c.color) for c in pal.colors]
assert got == [(1, 0, 0), (0, 1, 0)], got
print("our own history, newest first, each colour once")
# a stroke on the paper while painting is noted
assert bpy.ops.popup.paint() == {"FINISHED"}
from popup_pro import ops  # noqa: E402
assert ops.painting(bpy.context)
img = ops.painting_into(sc)
assert img is not None and img.name.startswith("Pop-up Art"), img
ts = bpy.context.tool_settings
ups = getattr(ts, "unified_paint_settings", None) or ts.image_paint.unified_paint_settings
owner = ups if (ups.use_unified_color or ts.image_paint.brush is None) else ts.image_paint.brush
owner.color = (0.2, 0.4, 0.6)
img.pixels[0] = 0.5  # the stroke
assert img.is_dirty
history._on_update(sc, None)
assert tuple(round(x, 3) for x in pal.colors[0].color) == (0.2, 0.4, 0.6), pal.colors[0].color[:]
print("a stroke on the paper notes its colour")
bpy.ops.popup.paint()
if PS:
    import paint_system  # noqa: E402
    paint_system.register()
    history.note(sc, (0, 0, 1))
    assert sc.ps_scene_data.color_history_palette is not None
    assert tuple(sc.ps_scene_data.color_history_palette.colors[0].color) == (0, 0, 1)
    print("with Paint System: into its history")
print("v54 ok")
