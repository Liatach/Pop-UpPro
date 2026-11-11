"""v0.38: Paint is one on/off toggle; Erase is a choice while painting (the
brush rubs the paper see-through), and painted holes are cut when asked
(Cut Painted Holes), or automatically only if Cut Automatically is on."""
# families: paint, holes
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402

bpy.ops.wm.read_factory_settings(use_empty=True)
import popup_pro as addon  # noqa: E402
from popup_pro import ops  # noqa: E402

addon.register()
sc = bpy.context.scene
st = sc.popup
assert bpy.ops.popup.build() == {"FINISHED"}
assert not st.auto_holes, "cutting painted holes waits to be asked"
assert bpy.ops.popup.paint() == {"FINISHED"}
b = sc.tool_settings.image_paint.brush
if b is None:
    print("no brush in this build of Blender; skipping the Erase checks")
else:
    before = b.blend
    assert bpy.ops.popup.paint_erase() == {"FINISHED"}
    assert ops.erasing(sc) and ops.painting_into(sc) == ops.paint_images(sc)[0]
    assert bpy.ops.popup.paint_erase() == {"FINISHED"}
    assert not ops.erasing(sc) and b.blend == before
    bpy.ops.popup.paint_erase()
    assert bpy.ops.popup.paint() == {"FINISHED"}  # off: the brush paints again
    assert b.blend == before
    print("Erase toggles the brush, and never stays on after painting")
assert bpy.context.mode == "OBJECT"
print("all v38 checks pass")
